import os
from types import ModuleType

from beanie import init_beanie
from mcp.server.fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.applications import Starlette

from papi.core.addons import (
    get_addons_from_dirs,
    get_beanie_documents_from_addon,
    get_router_from_addon,
    load_and_import_all_addons,
)
from papi.core.logger import logger
from papi.core.mcp import create_sse_server
from papi.core.router import MPCRouter
from papi.core.settings import get_config
from papi.core.utils import install_python_dependencies


async def init_base_system() -> tuple[dict[str, ModuleType], dict[str, type]]:
    """
    Initialize the base system by loading addons and setting up the database connection.

    This function performs the following steps:
    - Reads server configuration.
    - Initializes the MongoDB connection if enabled.
    - Loads addons from the base and extra paths specified in the configuration.
    - Imports each addon as a Python module.
    - Collects Beanie document models from each addon.
    - Initializes the Beanie ODM if documents and MongoDB are available.

    Returns:
        tuple:
            - A dictionary mapping addon IDs to imported modules.
            - A dictionary mapping document class names to their class definitions.

    Raises:
        RuntimeError: If addon loading fails due to misconfiguration or import errors.
    """
    config = get_config()
    mongo_db_enabled = bool(config.database.mongodb_uri)
    beanie_document_models = {}

    # Initialize MongoDB client if URI is provided
    client = (
        AsyncIOMotorClient(config.database.mongodb_uri) if mongo_db_enabled else None
    )

    # Define base and user-defined addon paths
    logger.info(f"Loading addons from: {config.addons.extra_addons_path}")
    base_addons_path = os.path.abspath(
        os.path.join(__file__, "..", "..", "base_addons")
    )
    addons_paths = [config.addons.extra_addons_path, base_addons_path]

    try:
        # Discover and import addons
        addons_graph = get_addons_from_dirs(
            addons_paths=addons_paths,
            enabled_addons_ids=config.addons.enabled,
        )
        python_deps = addons_graph.get_all_python_dependencies()
        if python_deps:
            install_python_dependencies(python_deps)

        modules = load_and_import_all_addons(addons_graph)
    except (ValueError, ImportError) as e:
        logger.exception(f"Failed to load addons: {e}")
        if mongo_db_enabled:
            client.close()
        raise RuntimeError("Addon loading failed") from e
    except Exception as e:
        logger.exception(f"Unexpected error while loading addons: {e}")
        modules = {}

    logger.info(f"  → Loaded {len(modules)} addons")

    # Process each addon module
    for addon_id, module in modules.items():
        addon = addons_graph.addons[addon_id]
        logger.debug(f"    • {addon.name} (v{addon.version}) by {addon.author}")

        # Register Beanie document models for each addon
        addon_documents = get_beanie_documents_from_addon(module)
        if addon_documents and mongo_db_enabled:
            doc_names = [doc.__name__ for doc in addon_documents]
            logger.debug(f"      → Documents: {', '.join(doc_names)}")
            beanie_document_models.update(dict(zip(doc_names, addon_documents)))

    # Initialize Beanie ODM with the collected documents
    if mongo_db_enabled and beanie_document_models:
        logger.info(
            f"Initializing database with {len(beanie_document_models)} document models"
        )
        await init_beanie(
            database=client.get_database(),
            document_models=beanie_document_models.values(),
        )

    return modules, beanie_document_models


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
        logger.debug(f"  -> Searching MCP tools in module: {module.__name__}")
        routers = get_router_from_addon(module)

        for router in routers:
            for route in router.routes:
                # Identify MCP tools either by router type or flag
                if isinstance(route, MPCRouter) or getattr(route, "is_mcp_tool", False):
                    name = route.endpoint.__name__
                    if name not in loaded_tools:
                        logger.debug(f"    • Adding MCP tool: {name}")
                        mcp_server.add_tool(route.endpoint)
                        loaded_tools.append(name)

    return create_sse_server(mcp_server) if as_sse else mcp_server
