"""
Main CLI interface and server runners for the pAPI system.

This module provides the command-line interface (CLI) for managing the pAPI system,
including launching the interactive shell, web server, and MCP server.

It also defines core utilities for system initialization, logging management,
and FastAPI application lifecycle handling.

Author: Eduardo M. Fírvida Donestevez
"""

import asyncio
import importlib
import importlib.metadata
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from textwrap import dedent
from typing import Any, AsyncGenerator, Dict, Set

import anyio
import click
import nest_asyncio
import uvicorn
from click_default_group import DefaultGroup
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from IPython.terminal.embed import InteractiveShellEmbed

from papi.core.addons import (
    get_router_from_addon,
    has_static_files,
)
from papi.core.db import get_redis_client
from papi.core.exceptions import APIException
from papi.core.init import init_base_system, init_mcp_server, shutdown_addons
from papi.core.logger import disable_logging, logger, setup_logging
from papi.core.models.config import GeneralInfoConfig
from papi.core.response import create_response
from papi.core.settings import get_config

__version__ = importlib.metadata.version("papi")


def get_banner() -> str:
    """
    Temporarily disable all logging within a context.

    Useful for suppressing noisy output during initialization
    or interactive shell startup.
    """
    version_str = f"v{__version__}" if not __version__.startswith("v") else __version__
    return dedent(rf"""
               _     ____   ___          ____  _            _  _ 
     ___      / \   |  _ \ |_ _|        / ___|| |__    ___ | || |
    |  _ \   / _ \  | |_) | | | _______ \___ \|  _ \  / _ \| || |
    | |_) | / ___ \ |  __/  | | |_____| ___) || | | ||  __/| || |
    |  __/ /_/   \_\|_|    |___|       |____/ |_| |_| \___||_||_|
    |_|                                      Version: {version_str}
    """)


def get_mcp_server(as_sse: bool = False) -> Any:
    """
    Initialize and return the MCP server instance.

    This function wraps the initialization of the base system and
    the MCP server, ensuring it runs in an isolated event loop.

    Args:
        as_sse (bool): Whether to configure the server for Server-Sent Events.

    Returns:
        Any: The initialized MCP server instance.

    Exits:
        Terminates the process with error code 1 on failure.
    """

    async def _init() -> Any:
        modules_extra = await init_base_system()
        return init_mcp_server(modules_extra, as_sse)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_init())
        loop.close()
        return result
    except Exception:
        logger.critical("Error initializing MCP Server", exc_info=True)
        sys.exit(1)


@asynccontextmanager
async def run_api_server(app: FastAPI) -> AsyncGenerator:
    """
    FastAPI lifespan context manager for application initialization and cleanup.

    Performs the following operations:
    1. Initializes the base system components
    2. Sets up Redis client connection
    3. Registers addon routes and static assets
    4. Mounts the MCP server endpoint
    5. Configures global storage directories
    6. Ensures proper resource cleanup on shutdown

    Args:
        app: FastAPI application instance to configure

    Yields:
        None: Control passes to the application runtime

    Raises:
        RuntimeError: For critical initialization failures
    """
    redis_client = None
    try:
        # Phase 1: System initialization
        logger.info("Initializing base system components...")
        base_system = await init_base_system()

        # Phase 2: Establish Redis connection
        logger.debug("Establishing Redis connection...")
        redis_client = await get_redis_client()

        # Phase 3: Addon registration
        loaded_routers: Set[Any] = set()
        modules = base_system.get("modules", {}) if base_system else {}

        for addon_id, module in modules.items():
            # Register addon routes
            if routers := get_router_from_addon(module):
                for router in routers:
                    if router not in loaded_routers:
                        app.include_router(router)
                        loaded_routers.add(router)
                logger.info(f"Addon '{addon_id}': Registered {len(routers)} routes")

            # Mount static assets
            if has_static_files(module):
                static_path = Path(module.__path__[0]) / "static"
                if static_path.is_dir():
                    app.mount(
                        f"/static/{addon_id}",
                        StaticFiles(directory=static_path),
                        name=f"{addon_id}_static",
                    )
                    logger.debug(
                        f"Addon '{addon_id}': Mounted static assets at {static_path}"
                    )
                else:
                    logger.warning(
                        f"Addon '{addon_id}': Missing static directory {static_path}"
                    )

        # Phase 4: MCP server setup
        if modules:
            mcp_server = init_mcp_server(modules, as_sse=True)
            app.mount("/mcp", mcp_server, name="MCP Tools")
            logger.info("Mounted MCP server at /mcp")

        # Phase 5: Storage configuration
        config = get_config()
        if config.storage:
            for name, path in config.storage.model_dump().items():
                os.makedirs(path, exist_ok=True)
                app.mount(
                    f"/storage/{name}",
                    StaticFiles(directory=path),
                    name=f"{name}_storage",
                )
                logger.info(f"Storage '{name}' mounted at: /storage/{name}")

        # Application ready
        logger.info("Application initialization completed successfully")
        yield

    except Exception as e:
        logger.critical(f"Application initialization failed: {str(e)}")
        raise RuntimeError("Critical startup failure") from e

    finally:
        # Phase 6: Resource cleanup
        logger.info("Starting application shutdown...")

        if modules:
            await shutdown_addons(modules)

        if redis_client:
            logger.debug("Closing Redis connection...")
            await redis_client.aclose()
            logger.info("Redis connection closed")
        logger.info("Shutdown completed")


def create_fastapi_app() -> FastAPI:
    """
    Creates and configures the main FastAPI application instance.

    This function:
    1. Retrieves application configuration
    2. Sets core API metadata (title, version, description)
    3. Attaches the lifespan management context
    4. Returns the fully configured application instance

    Returns:
        FastAPI: The configured application instance

    Raises:
        RuntimeError: If critical configuration is missing
    """
    try:
        logger.info("Creating FastAPI application instance")
        config = get_config()

        # Validate essential configuration
        if not config.info:
            logger.warning("Missing info configuration - using defaults")
            config.info = GeneralInfoConfig()  # Assume default config class exists

        # Create application with metadata
        app = FastAPI(
            title=config.info.title or "pAPI",
            version=config.info.version or __version__,
            description=config.info.description or "",
            lifespan=run_api_server,
        )

        logger.debug("FastAPI instance created successfully")
        return app

    except Exception as e:
        logger.critical("Failed to create FastAPI application", exc_info=True)
        raise RuntimeError("Application initialization failed") from e


def setup_api_exception_handler(app: FastAPI) -> None:
    """
    Registers a global exception handler for custom API exceptions.

    This handler:
    1. Catches APIException instances
    2. Structures consistent error responses
    3. Preserves error details and headers
    4. Returns standardized JSON error format

    Args:
        app: FastAPI application instance to register the handler

    Note:
        Must be called after app creation but before starting the server
    """

    @app.exception_handler(APIException)
    async def api_exception_handler(
        request: Request, exc: APIException
    ) -> JSONResponse:
        """
        Handles APIException errors and returns structured responses.

        Args:
            request: Incoming request object
            exc: Raised APIException instance

        Returns:
            JSONResponse: Formatted error response
        """
        # Log the error with appropriate severity
        if exc.status_code >= 500:
            logger.error(f"Server error ({exc.code}): {exc.message}")
        elif exc.status_code >= 400:
            logger.warning(f"Client error ({exc.code}): {exc.message}")

        # Create standardized error response
        error_response = create_response(
            success=False,
            message=exc.message,
            error={
                "code": exc.code,
                "detail": exc.detail,
                "message": exc.message,
                "status_code": exc.status_code,
            },
        )

        # Return JSON response with appropriate status
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=exc.headers or {},
        )

    logger.debug("Registered global API exception handler")


@click.group(
    cls=DefaultGroup,
    default="webserver",
    default_if_no_args=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Main entry point for pAPI service management CLI.",
)
@click.option(
    "--config",
    default="config.yaml",
    show_default=True,
    help="Path to configuration file. Default is '${PWD}/config.yaml'.",
)
@click.pass_context
def cli(ctx, config):
    if ctx.obj is None:
        ctx.obj = {}

    if not ctx.obj.get("_initialized", False):
        try:
            cfg = get_config(config)
            ctx.obj["config"] = cfg

            setup_logging()
            ctx.obj["_initialized"] = True
            logger.debug("CLI initialized successfully.")

        except Exception as e:
            logger.critical("Failed to initialize configuration or logging", exc_info=e)
            sys.exit(1)


@cli.command(name="shell")
def shell() -> None:
    """
    Launch an interactive IPython shell with the initialized system context.

    Provides:
    - Full async/await support
    - Pre-loaded document models
    - Helper functions for querying
    - All system components initialized
    - Addon modules available

    Usage:
    $ papi shell
    """
    nest_asyncio.apply()  # Enable nested event loops

    async def start_shell() -> None:
        """Initialize system and launch IPython shell."""
        try:
            with disable_logging():  # Suppress initialization logs
                base_system = await init_base_system() or {}

                # Prepare shell environment
                namespace: Dict[str, Any] = (
                    {k: v for k, v in base_system.items() if v} if base_system else {}
                )

                # Configure IPython shell
                shell = InteractiveShellEmbed(
                    banner1=get_banner(),
                    user_ns=namespace,
                    exit_msg="Exiting pAPI shell. Goodbye!",
                )
                shell.run_line_magic("autoawait", "asyncio")
                shell()

        except Exception as e:
            logger.critical(f"Failed to start interactive shell: {e}", exc_info=True)
            sys.exit(1)

    anyio.run(start_shell)


@cli.command(name="webserver")
def webserver() -> None:
    """
    Start the production FastAPI web server.

    Features:
    - Full API endpoint routing
    - Static asset serving
    - MCP integration
    - Custom exception handling

    Usage:
    $ papi webserver
    """
    try:
        logger.info("Creating FastAPI application")
        app = create_fastapi_app()
        setup_api_exception_handler(app)

        config = get_config()

        uvicorn_config = uvicorn.Config(
            app,
            host=config.server.host or "0.0.0.0",
            port=config.server.port or 8000,
            log_config=None,
            access_log=False,
            timeout_keep_alive=60,
        )

        server = uvicorn.Server(uvicorn_config)
        server.run()

    except Exception as e:
        logger.critical(f"Webserver startup failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command(name="mcpserver")
def mcpserver() -> None:
    """
    Start the standalone Management Control Protocol server.

    Runs the backend communication protocol without the full API stack.

    Usage:
    $ papi mcpserver
    """
    try:
        logger.info("Initializing MCP server")
        mcp = get_mcp_server(as_sse=False)
        logger.info("Starting MCP server in standalone mode")
        mcp.run()
    except Exception as e:
        logger.critical(f"MCP Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        cli(prog_name="papi")
    except Exception as e:
        logger.critical(f"CLI runtime error: {e}", exc_info=True)
        sys.exit(1)
