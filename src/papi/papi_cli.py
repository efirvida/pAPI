"""
Main CLI interface and server runners for the pAPI system.

This module provides the command-line interface (CLI) for managing the pAPI system,
including launching the interactive shell, web server, and MCP server.

It also defines core utilities for system initialization, logging management,
and FastAPI application lifecycle handling.

Author: Eduardo M. Fírvida Donestevez
"""

import asyncio
import functools
import importlib
import importlib.metadata
import logging
import os
import sys
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from textwrap import dedent
from typing import Any, Generator, Set

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
    get_addons_from_dirs,
    get_router_from_addon,
    has_static_files,
    load_and_import_all_addons,
)
from papi.core.cli import CLIRegistry
from papi.core.db import get_redis_client, query_helper
from papi.core.exceptions import APIException
from papi.core.init import init_base_system, init_mcp_server
from papi.core.logger import logger, setup_logging
from papi.core.models.response import create_response
from papi.core.settings import get_config

__version__ = importlib.metadata.version("papi")

# Initialize registry at module level
registry = CLIRegistry()


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


@contextmanager
def disable_logging() -> Generator[None, None, None]:
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

    async def _init() -> Any:
        modules_extra, _ = await init_base_system()
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
async def run_api_server(app: FastAPI) -> Generator[None, None, None]:
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
        base_system = await init_base_system()
        modules = base_system["modules"]
        redis = await get_redis_client()

        loaded_routers: Set[Any] = set()
        for addon_id, module in modules.items():
            if addon_routers := get_router_from_addon(module):
                for router in addon_routers:
                    if router not in loaded_routers:
                        app.include_router(router)
                        loaded_routers.add(router)
                logger.debug(
                    f"Addon {addon_id}: Registered {len(addon_routers)} routes"
                )

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

        mcp_server = init_mcp_server(modules, as_sse=True)
        app.mount("/", mcp_server, name="MCP Tools")

        config = get_config()
        for name, path in config.storage.model_dump().items():
            os.makedirs(path, exist_ok=True)
            app.mount(
                f"/{name}", StaticFiles(directory=path), name=f"Global {name} Storage"
            )
            logger.info(f"Storage '{name}' configured at: {path}")

        yield
        logger.info("Closing redis connection...")
        await redis.aclose()

    except Exception as e:
        logger.critical(f"Initialization error: {e}")
        raise


def discover_addon_commands() -> None:
    try:
        config = get_config()
        base_addons_path = os.path.abspath(os.path.join(__file__, "..", "base"))
        addons_paths = [
            p for p in [config.addons.extra_addons_path, base_addons_path] if p
        ]

        addons_graph = get_addons_from_dirs(
            addons_paths=addons_paths,
            enabled_addons_ids=config.addons.enabled,
        )
        modules = load_and_import_all_addons(addons_graph)

        for addon_id, module in modules.items():
            try:
                cli_module = importlib.import_module(f"{module.__package__}.cli")
                if hasattr(cli_module, "register_commands"):
                    cli_module.register_commands(registry, addon_id)
            except ImportError:
                continue
            except Exception as e:
                logger.warning(
                    f"Failed to register CLI for addon '{addon_id}': {e}", exc_info=True
                )

    except Exception as e:
        logger.critical(f"Addon discovery failed: {e}", exc_info=True)


def create_fastapi_app() -> FastAPI:
    config = get_config()
    return FastAPI(
        title=config.info.title or "pAPI",
        version=config.info.version or __version__,
        description=config.info.description or "",
        lifespan=run_api_server,
    )


def setup_api_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(APIException)
    async def api_exception_handler(
        request: Request, exc: APIException
    ) -> JSONResponse:
        response = create_response(
            success=False,
            message=exc.message,
            error={
                "code": exc.code,
                "detail": exc.detail,
                "message": exc.message,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
            headers=exc.headers,
        )


@click.group(
    cls=DefaultGroup,
    default="webserver",
    default_if_no_args=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Main entry point for pAPI service management CLI.",
)
@click.option("--config", default="config.yaml", help="Path to configuration file")
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """
    Main entry point for pAPI service management CLI.

    Provides subcommands to launch the system in different modes,
    including interactive shell, web server, and MCP server.

    """
    ctx.ensure_object(dict)
    ctx.obj["CONFIG_PATH"] = config


def init_logging_and_config(ctx: click.Context) -> None:
    if not hasattr(ctx, "obj_initialized"):
        try:
            ctx.obj["CONFIG"] = get_config(ctx.obj["CONFIG_PATH"])
            setup_logging()
            ctx.obj_initialized = True
        except Exception as e:
            logger.critical(f"Error initializing system: {e}")
            sys.exit(1)


@cli.command()
def shell() -> None:
    """
    Launch an interactive IPython shell with the initialized system context.

    This includes all Beanie documents and addon modules, fully initialized and
    ready for inspection or manual testing. Async/await is fully supported.
    """
    ctx = click.get_current_context()
    init_logging_and_config(ctx)
    nest_asyncio.apply()

    async def start_shell() -> None:
        try:
            with disable_logging():
                base_system = await init_base_system()
                documents = base_system.get("documents", {})

                def show_models() -> None:
                    print("Available document models:")
                    for name in documents:
                        print(f" - {name}")

                def env(model_name: str) -> Any:
                    return documents.get(model_name)

                helpers = {
                    "env": env,
                    "show_models": show_models,
                    "sql_query": query_helper,
                }

                user_namespace = {
                    **{k: v for k, v in base_system.items() if v},
                    **helpers,
                }

                shell = InteractiveShellEmbed(
                    banner1=get_banner(), user_ns=user_namespace
                )
                shell.run_line_magic("autoawait", "asyncio")
                shell()

        except Exception as e:
            logger.critical(f"Failed to start interactive shell: {e}")
            sys.exit(1)

    anyio.run(start_shell)


@cli.command()
def webserver() -> None:
    """
    Start the production FastAPI web server.

    Loads configuration from file and initializes the full system via
    the FastAPI lifespan context. Runs the server with Uvicorn.
    """
    ctx = click.get_current_context()
    init_logging_and_config(ctx)

    app = create_fastapi_app()
    setup_api_exception_handler(app)

    config = get_config()
    uvicorn_config = uvicorn.Config(
        app,
        host=config.server.host or "0.0.0.0",
        port=config.server.port or 8000,
        log_config=None,
        access_log=False,
    )

    server = uvicorn.Server(uvicorn_config)
    server.run()


@cli.command()
def mcpserver() -> None:
    """
    Start the standalone MCP server.

    This runs the backend communication protocol server without launching the full API.
    """
    ctx = click.get_current_context()
    init_logging_and_config(ctx)

    try:
        mcp = get_mcp_server(as_sse=False)
        mcp.run()
    except Exception as e:
        logger.critical(f"MCP Server error: {e}")
        sys.exit(1)


def create_wrapper(original: Any) -> Any:
    @functools.wraps(original)
    def wrapped_command(*args: Any, **kwargs: Any) -> Any:
        click.echo(get_banner())
        ctx = click.get_current_context()
        init_logging_and_config(ctx)
        return original(*args, **kwargs)

    return wrapped_command


discover_addon_commands()
dynamic_cli_group = registry.create_cli()

for command_name, command in dynamic_cli_group.commands.items():
    if command_name in cli.commands:
        continue
    if isinstance(command, click.Group):
        cli.add_command(command, command_name)
        continue
    original_callback = command.callback
    if original_callback is None:
        logger.warning(f"Command '{command_name}' has no callback and was skipped.")
        continue
    if not callable(original_callback):
        raise TypeError(f"Command '{command_name}' callback is not callable.")
    command.callback = create_wrapper(original_callback)
    cli.add_command(command, command_name)

if __name__ == "__main__":
    print(get_banner())
    cli()
