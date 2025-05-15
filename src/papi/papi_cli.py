"""
Main CLI interface and server runners for the pAPI system.

This module provides the command-line interface (CLI) for managing the pAPI system,
including launching the interactive shell, web server, and MCP server.

It also defines core utilities for system initialization, logging management,
and FastAPI application lifecycle handling.

Author: Eduardo M. Fírvida Donestevez
"""

import asyncio
import importlib.metadata
import logging
import os
import sys
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

import click
import uvicorn
from click_default_group import DefaultGroup
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from papi.core.addons import get_router_from_addon, has_static_files
from papi.core.init import init_base_system, init_mcp_server
from papi.core.logger import logger, setup_logging
from papi.core.settings import get_config

__version__ = importlib.metadata.version("papi")


@contextmanager
def disable_logging():
    """
    Temporarily disable all logging within a context.

    Useful for suppressing noisy output during initialization
    or interactive shell startup.
    """
    previous_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous_level)


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

    async def _init():
        modules_extra, _ = await init_base_system()
        return init_mcp_server(modules_extra, as_sse)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_init())
    except Exception as e:
        logger.error(f"Error initializing MCP Server: {e}")
        sys.exit(1)


@asynccontextmanager
async def run_api_server(app: FastAPI):
    """
    FastAPI lifespan context manager for initializing the web server.

    This sets up addon routes, static file mounts, and MCP tools. It also prepares
    global storage directories defined in the configuration.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None

    Raises:
        Exception: If initialization fails, it logs the error and re-raises.
    """
    try:
        modules, _ = await init_base_system()

        # Register addons
        for addon_id, module in modules.items():
            if addon_routers := get_router_from_addon(module):
                for router in addon_routers:
                    app.include_router(router)
                logger.debug(
                    f"Addon {addon_id}: Registered {len(addon_routers)} routes"
                )

            # Serve static files if present
            if has_static_files(module):
                static_path = Path(module.__path__[0]) / "static"
                if static_path.exists() and static_path.is_dir():
                    app.mount(
                        f"/{addon_id}",
                        StaticFiles(directory=static_path),
                        name=f"{addon_id}_static",
                    )
                else:
                    logger.warning(
                        f"Addon {addon_id}: Missing static directory at {static_path}"
                    )

        # Mount MCP server tools
        mcp_server = init_mcp_server(modules, as_sse=True)
        app.mount("/", mcp_server, name="MCP Tools")

        # Configure global storage
        config = get_config()
        for name, path in config.storage.model_dump().items():
            os.makedirs(path, exist_ok=True)
            app.mount(
                f"/{name}",
                StaticFiles(directory=path),
                name=f"Global {name} Storage",
            )
            logger.info(f"Storage '{name}' configured at: {path}")

        yield
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise


@click.group(cls=DefaultGroup, default="webserver", default_if_no_args=True)
@click.option("--config", default="config.yaml", help="Path to configuration file")
@click.pass_context
def cli(ctx, config: str):
    """
    Main entry point for pAPI service management CLI.

    Provides subcommands to launch the system in different modes,
    including interactive shell, web server, and MCP server.

    """
    ctx.ensure_object(dict)
    try:
        ctx.obj["CONFIG"] = get_config(config)
        setup_logging()
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)


@cli.command()
def shell():
    """
    Launch an interactive IPython shell with the initialized system context.

    This includes all Beanie documents and addon modules, fully initialized and
    ready for inspection or manual testing. Async/await is fully supported.
    """

    from textwrap import dedent

    import anyio
    import nest_asyncio
    from IPython.terminal.embed import InteractiveShellEmbed

    nest_asyncio.apply()

    async def start_shell():
        try:
            with disable_logging():
                addons, beanie_documents = await init_base_system()

                def show_models():
                    print("Available document models:")
                    for name in beanie_documents:
                        print(f" - {name}")

                def env(model_name: str):
                    return beanie_documents[model_name]

                helpers = {
                    "env": env,
                    "show_models": show_models,
                }
                user_namespace = {
                    "documents": beanie_documents,
                    "addons": addons,
                    **helpers,
                }

                version_str = (
                    f"v{__version__}"
                    if not __version__.startswith("v")
                    else __version__
                )

                header = dedent(rf"""
                           _     ____   ___          ____  _            _  _ 
                 ___      / \   |  _ \ |_ _|        / ___|| |__    ___ | || |
                |  _ \   / _ \  | |_) | | | _______ \___ \|  _ \  / _ \| || |
                | |_) | / ___ \ |  __/  | | |_____| ___) || | | ||  __/| || |
                |  __/ /_/   \_\|_|    |___|       |____/ |_| |_| \___||_||_|
                |_|                                      Version: {version_str}
                """)

                shell = InteractiveShellEmbed(
                    banner1=header,
                    user_ns=user_namespace,
                )

                # Ensure autoawait is enabled with asyncio
                shell.run_line_magic("autoawait", "asyncio")
                shell()

        except Exception as e:
            logger.error(f"Failed to start interactive shell: {e}")
            sys.exit(1)

    anyio.run(start_shell)


@cli.command()
def webserver():
    """
    Start the production FastAPI web server.

    Loads configuration from file and initializes the full system via
    the FastAPI lifespan context. Runs the server with Uvicorn.
    """
    config = get_config()
    app = FastAPI(
        title=config.info.title or "pAPI",
        version=config.info.version or __version__,
        description=config.info.description or "",
        logger=logger,
        lifespan=run_api_server,
    )

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=None,
        log_config=None,
    )


@cli.command()
def mcpserver():
    """
    Start the standalone MCP server.

    This runs the backend communication protocol server without launching the full API.
    """
    try:
        mcp = get_mcp_server(as_sse=False)
        mcp.run()
    except Exception as e:
        logger.error(f"MCP Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
