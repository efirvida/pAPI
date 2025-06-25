from types import ModuleType
from typing import Callable, Optional, Type

from beanie import init_beanie
from mcp.server.fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeMeta
from starlette.applications import Starlette

from papi.core.addons import (
    AddonSetupHook,
    get_addon_setup_hooks,
    get_addons_from_dir,
    get_beanie_documents_from_addon,
    get_router_from_addon,
    get_sqlalchemy_models_from_addon,
    load_and_import_all_addons,
)
from papi.core.db import (
    create_database_if_not_exists,
    extract_bases_from_models,
    get_redis_client,
)
from papi.core.logger import logger
from papi.core.mcp import create_sse_server
from papi.core.router import MPCRouter
from papi.core.settings import get_config
from papi.core.utils import install_python_dependencies


async def startup_addons(modules: dict[str, ModuleType]) -> None:
    """
    Initializes and executes startup hooks for all registered addon modules.

    Args:
        modules (dict[str, ModuleType]): A dictionary mapping addon IDs to their loaded modules.

    This function retrieves all startup hook factories from each module using `get_addon_setup_hooks`,
    instantiates each hook, and calls its `startup()` coroutine.
    """
    for addon_id, module in modules.items():
        logger.debug(f"Initializing startup hooks for addon '{addon_id}'")
        hook_factories: list[Callable[[], AddonSetupHook]] = get_addon_setup_hooks(
            module
        )

        for factory in hook_factories:
            try:
                hook = factory()
                await hook.startup()
                logger.debug(f"Startup completed for addon '{addon_id}' hook: {hook}")
            except Exception as e:
                logger.exception(f"Error during startup of addon '{addon_id}': {e}")


async def shutdown_addons(modules: dict[str, ModuleType]) -> None:
    """
    Initializes and executes shutdown hooks for all registered addon modules.

    Args:
        modules (dict[str, ModuleType]): A dictionary mapping addon IDs to their loaded modules.

    This function retrieves all shutdown hook factories from each module using `get_addon_setup_hooks`,
    instantiates each hook, and calls its `shutdown()` coroutine.
    """
    for addon_id, module in modules.items():
        logger.debug(f"Initializing shutdown hooks for addon '{addon_id}'")
        hook_factories: list[Callable[[], AddonSetupHook]] = get_addon_setup_hooks(
            module
        )

        for factory in hook_factories:
            try:
                hook = factory()
                await hook.shutdown()
                logger.debug(f"Shutdown completed for addon '{addon_id}' hook: {hook}")
            except Exception as e:
                logger.exception(f"Error during shutdown of addon '{addon_id}': {e}")


async def init_mongodb_beanie(
    config, modules: dict[str, ModuleType]
) -> dict[str, type]:
    """
    Initializes MongoDB (via Beanie) if documents are found and configuration is valid.

    This function:
    - Scans loaded modules for Beanie document models.
    - Logs a warning or error if documents are found but no MongoDB URI is configured.
    - Initializes the Beanie ODM if both are present.

    Args:
        config: The server configuration object.
        modules: Dictionary of loaded addon modules.

    Returns:
        A dictionary mapping document class names to their class definitions.

    Raises:
        RuntimeError: If Beanie documents are found but MongoDB URI is missing.
    """
    beanie_document_models = {}

    # Buscar documentos en los módulos
    logger.info("Searching for MongoDB documents in active addons")
    for addon_id, module in modules.items():
        addon_documents = get_beanie_documents_from_addon(module)
        if addon_documents:
            doc_names = [doc.__name__ for doc in addon_documents]
            logger.debug(f"  → Documents from '{addon_id}': {', '.join(doc_names)}")
            beanie_document_models.update(dict(zip(doc_names, addon_documents)))

    if beanie_document_models and not config.database.mongodb_uri:
        logger.error("Found Beanie document models but MongoDB URI is not configured.")
        raise RuntimeError("MongoDB URI required to initialize Beanie document models.")

    if not beanie_document_models:
        logger.info("No Beanie document models found. Skipping MongoDB initialization.")
        return {}

    client = AsyncIOMotorClient(config.database.mongodb_uri)
    try:
        logger.info(
            f"Initializing MongoDB with {len(beanie_document_models)} document models"
        )
        await init_beanie(
            database=client.get_database(),
            document_models=beanie_document_models.values(),
        )

    except ServerSelectionTimeoutError:
        logger.exception("MongoDB connection timeout.")
        raise RuntimeError("MongoDB Server connection timeout.")
    except PyMongoError as exc:
        logger.exception("MongoDB Server connection error.")
        raise RuntimeError(f"MongoDB Server connection error: {exc!r}")

    return beanie_document_models


async def init_sqlalchemy(
    config,
    modules: dict[str, ModuleType],
    create_tables: bool = True,
) -> Optional[dict[str, Type[DeclarativeMeta]]]:
    """
    Initializes SQLAlchemy models from addon modules and optionally creates tables
    for all detected Base metadata classes.

    Args:
        config: Configuration object with database URI.
        modules: Dictionary of addon modules.
        create_tables: Whether to automatically create tables in DB.

    Returns:
        Dict mapping model names to model classes, or None if no models found.

    Raises:
        RuntimeError: If DB URI missing or SQLAlchemy initialization fails.
    """
    sqlalchemy_models: dict[str, Type[DeclarativeMeta]] = {}

    logger.info("Searching for SQLAlchemy models in active addons")
    for addon_id, module in modules.items():
        addon_models = get_sqlalchemy_models_from_addon(module)
        if addon_models:
            model_names = [model.__name__ for model in addon_models]
            logger.debug(
                f"  → SQLAlchemy models from '{addon_id}': {', '.join(model_names)}"
            )
            sqlalchemy_models.update({
                name: model for name, model in zip(model_names, addon_models)
            })

    if not sqlalchemy_models:
        logger.info("No SQLAlchemy models found. Skipping SQLAlchemy initialization.")
        return None

    if not config.database.sql_uri:
        logger.error("SQL models found but no SQL URI configured.")
        raise RuntimeError("SQLAlchemy URI is required to initialize database models.")

    bases = extract_bases_from_models(sqlalchemy_models)

    sql_alchemy_cfg = config.database.get_backend("sqlalchemy").get_defined_fields()

    try:
        await create_database_if_not_exists(sql_alchemy_cfg["url"])

        engine: AsyncEngine = create_async_engine(**sql_alchemy_cfg)

        logger.info(
            f"SQLAlchemy engine initialized with {len(sqlalchemy_models)} models."
        )

        if create_tables:
            if not bases:
                logger.warning(
                    "No Base classes detected to create tables for. Skipping table creation."
                )
            else:
                async with engine.begin() as conn:
                    for base in bases:
                        logger.debug(f"Creating tables for Base: {base}")
                        await conn.run_sync(base.metadata.create_all)
                logger.info("All tables for specified Base(s) created successfully.")

        return sqlalchemy_models

    except SQLAlchemyError as exc:
        logger.exception("SQLAlchemy initialization failed.")
        raise RuntimeError(f"SQLAlchemy initialization error: {exc!r}")


async def init_base_system(init_db_system: bool = True) -> dict | None:
    """
    Initialize the base system by loading addons and initializing the database.

    Returns:
        tuple:
            - A dictionary mapping addon IDs to imported modules.
            - A dictionary mapping document class names to their class definitions.

    Raises:
        RuntimeError: If addon loading fails due to misconfiguration or import errors.
    """
    config = get_config()

    # Define addon paths
    logger.info(f"Loading addons from: {config.addons.extra_addons_path}")
    addons_path = config.addons.extra_addons_path

    try:
        # Discover and import addons
        addons_graph = get_addons_from_dir(
            addons_path=addons_path,
            enabled_addons_ids=config.addons.enabled,
        )
        if not addons_graph:
            return

        python_deps = addons_graph.get_all_python_dependencies()
        if python_deps:
            install_python_dependencies(python_deps)

        modules = load_and_import_all_addons(addons_graph)

    except (ValueError, ImportError) as e:
        logger.exception(f"Failed to load addons: {e}")
        raise RuntimeError("Addon loading failed") from e
    except Exception as e:
        logger.exception(f"Unexpected error while loading addons: {e}")
        modules = {}

    logger.info(f"Loaded {len(modules)} addons")

    for addon_id in modules:
        addon = addons_graph.addons[addon_id]
        logger.debug(f"  → {addon.name} (v{addon.version}) by {addon.authors}")

    if init_db_system and config.database:
        # Init MongoDB Documents, and Beanie models on system Startup.
        if config.database.mongodb_uri:
            beanie_document_models = await init_mongodb_beanie(config, modules)
        else:
            beanie_document_models = []

        # Init SQL models and create tables on system Startup if tables not exist
        if config.database.sql_uri:
            sql_models = await init_sqlalchemy(config, modules)
        else:
            sql_models = []

        # cache Redis client on startup
        if config.database.redis_uri:
            await get_redis_client()
    else:
        beanie_document_models = []
        sql_models = []

    await startup_addons(modules)

    return {
        "modules": modules,
        "mongo_documents": beanie_document_models,
        "sql_models": sql_models,
    }


def init_mcp_server(
    modules: dict[str, ModuleType], as_sse: bool = False
) -> Starlette | FastMCP:
    """
    Initialize the MCP (Model Context Protocol) server and register its tools.

    MCP tools are discovered from the loaded addon modules. Tools are registered
    by inspecting routes marked as `MPCRouter` instances or the Routes marked
    with the `is_mcp_tool` flag attribute.

    Args:
        modules (dict[str, ModuleType]): A dictionary of loaded addon modules.
        as_sse (bool, optional): If True, the server is wrapped as a Starlette SSE app. Defaults to False.

    Returns:
        Starlette | FastMCP: The configured FastMCP instance, optionally as a Starlette app for SSE.
    """
    mcp_server = FastMCP()
    logger.info("Initializing MCP tools...")

    for module in modules.values():
        loaded_tools = []
        logger.debug(f"  → Searching MCP tools in module: {module.__name__}")
        routers = get_router_from_addon(module)

        for router in routers:
            for route in router.routes:
                # Identify MCP tools either by router type or flag
                if isinstance(route, MPCRouter) or getattr(route, "is_mcp_tool", False):
                    name = route.endpoint.__name__
                    if name not in loaded_tools:
                        logger.debug(f"  → Adding MCP tool: {name}")
                        mcp_server.add_tool(route.endpoint)
                        loaded_tools.append(name)

    return create_sse_server(mcp_server) if as_sse else mcp_server
