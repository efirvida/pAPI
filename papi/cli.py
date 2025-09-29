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

try:
    import granian
except ImportError:
    granian = None
from click_default_group import DefaultGroup
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from IPython.terminal.embed import InteractiveShellEmbed
from starlette.exceptions import HTTPException

from papi.core.apps import get_router_from_app, has_static_files
from papi.core.db import get_redis_client
from papi.core.exceptions import APIException
from papi.core.init import init_base_system, init_mcp_server, shutdown_apps
from papi.core.logger import disable_logging, logger, setup_logging
from papi.core.models.config import (
    FastAPIAppConfig,
    GranianServerConfig,
    ServerConfig,
    ServerType,
    UvicornServerConfig,
)
from papi.core.response import create_response
from papi.core.settings import get_config

__version__ = importlib.metadata.version("papi")


def create_fastapi_app_for_granian():
    """
    Create FastAPI app specifically for Granian server.

    This wrapper function creates and returns a FastAPI application
    that can be used directly by Granian as an ASGI app.
    """
    app = create_fastapi_app()
    setup_api_exception_handler(app)
    return app


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
    3. Registers app routes and static assets
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

        # Phase 3: App registration
        loaded_routers: Set[Any] = set()
        modules = base_system.get("modules", {}) if base_system else {}

        for app_id, module in modules.items():
            # Register app routes
            if routers := get_router_from_app(module):
                for router in routers:
                    if router not in loaded_routers:
                        app.include_router(router)
                        loaded_routers.add(router)
                logger.info(f"App '{app_id}': Registered {len(routers)} routes")

            # Mount static assets
            if has_static_files(module):
                static_path = Path(module.__path__[0]) / "static"
                if static_path.is_dir():
                    app.mount(
                        f"/{app_id}",
                        StaticFiles(directory=static_path),
                        name=f"{app_id}_static",
                    )
                    logger.debug(
                        f"App '{app_id}': Mounted static assets at {static_path}"
                    )
                else:
                    logger.warning(
                        f"App '{app_id}': Missing static directory {static_path}"
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
            await shutdown_apps(modules)

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
            config.info = FastAPIAppConfig()  # Assume default config class exists

        info_fields = config.info.defined_fields()

        # Create application with metadata
        app = FastAPI(**info_fields, lifespan=run_api_server)

        logger.debug("FastAPI instance created successfully")
        return app

    except Exception as e:
        logger.critical("Failed to create FastAPI application", exc_info=True)
        raise RuntimeError("Application initialization failed") from e


def setup_api_exception_handler(app: FastAPI) -> None:
    """
    Registers global exception handlers for API exceptions and HTTP errors.

    This handler:
    1. Catches APIException instances
    2. Catches HTTP exceptions (404, 405, etc.)
    3. Structures consistent error responses
    4. Preserves error details and headers
    5. Returns standardized JSON error format

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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """
        Handles HTTP exceptions (404, 405, etc.) with custom pAPI responses.

        Args:
            request: Incoming request object
            exc: Raised HTTPException instance

        Returns:
            JSONResponse: Formatted error response
        """
        # Create user-friendly messages for common HTTP errors
        status_messages = {
            404: "The requested resource could not be found",
            405: "Method not allowed for this endpoint",
            422: "Invalid request data provided",
            500: "Internal server error occurred",
        }

        # Get user-friendly message or use default
        user_message = status_messages.get(exc.status_code, str(exc.detail))

        # Log the error appropriately
        if exc.status_code >= 500:
            logger.error(
                f"HTTP {exc.status_code}: {user_message} - Path: {request.url.path}"
            )
        elif exc.status_code >= 400:
            logger.warning(
                f"HTTP {exc.status_code}: {user_message} - Path: {request.url.path}"
            )

        # Create standardized error response using pAPI format
        error_response = create_response(
            success=False,
            message=user_message,
            error={
                "code": f"HTTP_{exc.status_code}",
                "detail": str(exc.detail),
                "message": user_message,
                "status_code": exc.status_code,
                "path": str(request.url.path),
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=getattr(exc, "headers", None) or {},
        )

    logger.debug("Registered global API exception handlers")


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
    - App modules available

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
@click.option(
    "--server",
    type=click.Choice(["granian", "uvicorn"]),
    help="Server type to use (overrides config)",
)
def webserver(server: str | None = None) -> None:
    """
    Start the production FastAPI web server.

    Features:
    - Full API endpoint routing
    - Static asset serving
    - MCP integration
    - Custom exception handling
    - Choice between Granian (default, high-performance) and Uvicorn servers

    Usage:
    $ papi webserver                    # Uses Granian by default
    $ papi webserver --server granian   # Explicitly use Granian
    $ papi webserver --server uvicorn   # Use Uvicorn instead
    """
    try:
        logger.info("Creating FastAPI application")
        app = create_fastapi_app()
        setup_api_exception_handler(app)

        config = get_config()

        if not config.server:
            logger.warning("Missing server configuration - using Granian defaults")
            config.server = ServerConfig()

        # Override server type if specified via CLI
        if server:
            config.server.type = (
                ServerType.GRANIAN if server == "granian" else ServerType.UVICORN
            )

        # Get the appropriate server configuration
        server_config = config.server.get_server_config()

        if config.server.type == ServerType.GRANIAN:
            if granian is None:
                logger.error(
                    "Granian is not installed. Install it with: pip install granian"
                )
                logger.info("Falling back to Uvicorn...")
                config.server.type = ServerType.UVICORN
                server_config = config.server.uvicorn or UvicornServerConfig()
                _run_uvicorn_server(app, server_config)
            else:
                logger.info("Starting Granian server...")
                if isinstance(server_config, GranianServerConfig):
                    _run_granian_server(app, server_config)
                else:
                    logger.error("Invalid Granian configuration")
                    sys.exit(1)
        else:
            # Use Uvicorn
            logger.info("Starting Uvicorn server...")
            if isinstance(server_config, UvicornServerConfig):
                _run_uvicorn_server(app, server_config)
            else:
                logger.error("Invalid Uvicorn configuration")
                sys.exit(1)

    except Exception as e:
        logger.critical(f"Webserver startup failed: {e}", exc_info=True)
        sys.exit(1)


def _run_granian_server(app: FastAPI, config: GranianServerConfig) -> None:
    """Run the application using Granian server."""
    import os
    import signal
    import subprocess
    import sys

    try:
        # Use Granian CLI directly to avoid ASGI/RSGI interface issues
        logger.info(
            f"Starting Granian server on {config.host}:{config.port} with {config.workers} workers"
        )

        # Build granian command with proper interface
        cmd = [
            sys.executable,
            "-m",
            "granian",
            "--interface",
            "asgi",  # Explicitly set ASGI interface
            "--host",
            config.host,
            "--port",
            str(config.port),
            "--workers",
            str(config.workers),
            "--factory",  # Important: tells granian to call the function
            "papi.cli:create_fastapi_app_for_granian",
        ]

        # Add optional parameters
        if getattr(config, "reload", False):
            cmd.extend(["--reload"])

        if getattr(config, "access_log", False):
            cmd.extend(["--access-log"])

        logger.debug(f"Granian command: {' '.join(cmd)}")

        # Start the granian process with new process group
        process = subprocess.Popen(cmd, preexec_fn=os.setsid)

        # Flag to prevent multiple shutdowns
        shutdown_initiated = False

        # Set up signal handling for graceful shutdown
        def signal_handler(signum, frame):
            nonlocal shutdown_initiated
            if shutdown_initiated:
                logger.debug(
                    f"Signal {signum} received but shutdown already in progress"
                )
                return

            shutdown_initiated = True
            logger.info(f"Received signal {signum}, shutting down Granian server...")

            try:
                # Send SIGTERM to the entire process group to ensure all workers are terminated
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)

                # Give it some time to shut down gracefully
                try:
                    process.wait(timeout=5)
                    logger.info("Granian server shut down gracefully")
                except subprocess.TimeoutExpired:
                    logger.debug(
                        "Granian server taking longer to shut down, checking process status..."
                    )
                    # Check if process is still running before forcing termination
                    if process.poll() is None:
                        logger.info("Forcing termination of Granian server...")
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                            process.wait(timeout=3)
                            logger.debug("Granian server terminated successfully")
                        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                            # Process might have already terminated, this is normal
                            logger.debug("Process cleanup completed")
                    else:
                        logger.debug("Process already terminated")

            except (ProcessLookupError, OSError):
                # Process was already terminated or doesn't exist - this is normal
                logger.debug("Process already terminated or cleaned up")
            except Exception as e:
                logger.warning(f"Unexpected error during shutdown: {e}")

            sys.exit(0)

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

        # Wait for the process to complete
        try:
            return_code = process.wait()
            if return_code != 0:
                logger.error(f"Granian process exited with code {return_code}")
                sys.exit(return_code)
        except KeyboardInterrupt:
            # This should be handled by the signal handler, but just in case
            if not shutdown_initiated:
                logger.info("Keyboard interrupt received, shutting down...")
                signal_handler(signal.SIGINT, None)

    except ImportError:
        logger.critical("Granian is not installed. Install with: pip install granian")
        raise
    except subprocess.CalledProcessError as e:
        logger.critical(f"Granian process failed with exit code {e.returncode}")
        raise
    except Exception as e:
        logger.critical(f"Granian server error: {e}", exc_info=True)
        raise


def _run_uvicorn_server(app: FastAPI, config: UvicornServerConfig) -> None:
    """Run the application using Uvicorn server."""
    try:
        uvicorn_config = uvicorn.Config(
            app, log_config=None, access_log=False, **config.defined_fields()
        )
        server = uvicorn.Server(uvicorn_config)
        server.run()
    except Exception as e:
        logger.critical(f"Uvicorn server error: {e}", exc_info=True)
        raise


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
