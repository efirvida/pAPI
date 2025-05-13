import os
from contextlib import asynccontextmanager
from pathlib import Path

from beanie import init_beanie
from core.addons import (
    get_addons_from_dirs,
    get_beanie_documents_from_addon,
    get_router_from_addon,
    has_static_files,
    load_and_import_all_addons,
)
from core.settings import get_config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from papi.core.logger import logger
from papi.core.mcp import create_sse_server, mcp_server
from papi.core.router import APIRoute

server_config = get_config()


@asynccontextmanager
async def startup_server(app: FastAPI):
    """Initialize application services, addons, and database."""
    beanie_document_models = []

    mongo_db_enabled = False

    # Init database connection
    if server_config.database.mongodb_uri:
        client = AsyncIOMotorClient(server_config.database.mongodb_uri)
        mongo_db_enabled = True

    # Load addons from configured paths
    logger.info("Loading addons from: %s", server_config.addons.extra_addons_path)

    base_addons_path = os.path.abspath(
        os.path.join(__file__, "..", "..", "base_addons")
    )
    enabled_addons_ids = server_config.addons.enabled

    try:
        addons_graph = get_addons_from_dirs(
            (
                server_config.addons.extra_addons_path,
                base_addons_path,
            ),
            enabled_addons_ids,
        )
        modules = load_and_import_all_addons(addons_graph)
    except (ValueError, ImportError) as e:
        logger.exception("Failed to load addons")
        raise RuntimeError("Addon initialization failed") from e

    logger.info("  → Loaded %d addons:", len(modules))

    for addon_id, module in modules.items():
        addon = addons_graph.addons[addon_id]
        logger.debug("    • %s (v%s) by %s", addon.name, addon.version, addon.author)

        # Register document models
        addon_docs = get_beanie_documents_from_addon(module)
        if addon_docs and mongo_db_enabled:
            doc_names = [cls.__name__ for cls in addon_docs]
            logger.debug("      → Documents: %s", ", ".join(doc_names))
            beanie_document_models.extend(addon_docs)

        # Register addons routes
        addon_routers = get_router_from_addon(module)
        if addon_routers:
            for router in addon_routers:
                # extend the rutes instead of use include router
                # to prevent missing the is_mcp_tool attribute in
                # the route due to reruting the fastapi internal
                # re-route procedure in include ruter
                # this works now but mybe can cause some issues and
                # we need to reimplement the include_ruter
                app.routes.extend(router.routes)
            logger.debug("      → Routers added: %d", len(addon_routers))

        # Mount static files
        if has_static_files(module):
            static_path = Path(module.__path__[0]) / "static"
            logger.debug("      → Static files path: %s", static_path)
            app.mount(
                f"/{addon_id}",
                StaticFiles(directory=static_path),
                name=f"{addon_id}_static",
            )

    # Register MCP tools from route endpoints
    logger.info("Searching for MCP tools...")
    for route in app.routes:
        if isinstance(route, APIRoute):
            if route.is_mcp_tool:
                logger.debug("    • Adding MCP tool: %s ", route.endpoint.__name__)
                mcp_server.add_tool(route.endpoint)

    logger.info("  → Loaded %d MCP Tools", len(mcp_server._tool_manager.list_tools()))

    # Mount MCP as SSE server
    app.mount("/", create_sse_server(mcp_server), name="MCP Tools")

    # Initialize database
    if mongo_db_enabled and beanie_document_models:
        logger.info(
            "Initializing database with %d document models",
            len(beanie_document_models),
        )
        await init_beanie(
            database=client.get_database(),
            document_models=beanie_document_models,
        )

    # Setup global file storage
    for name, path in server_config.storage.dict().items():
        os.makedirs(path, exist_ok=True)
        app.mount(
            f"/{name}",
            StaticFiles(directory=path),
            name=f"Global {name} Storage",
        )
        logger.info(f"Initializing global '{name}' storage folder in: '{path}'")

    yield


pAPI = FastAPI(
    title=server_config.info.title,
    lifespan=startup_server,
    logger=logger,
)
