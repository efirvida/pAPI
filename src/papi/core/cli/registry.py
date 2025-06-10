"""
CLI Registry for pAPI.

This module provides the central registry for CLI commands, allowing addons to
register their commands dynamically. The registry manages command namespacing
and ensures commands from different addons don't conflict.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Union

import click

from .base import PAPICommand, PAPICommandGroup


class CLIRegistry:
    """Central registry for pAPI CLI commands."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CLIRegistry, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the registry."""
        self._commands: Dict[str, Dict[str, Union[PAPICommand, PAPICommandGroup]]] = (
            defaultdict(dict)
        )
        self._root_group: Optional[PAPICommandGroup] = None

    def register_command(
        self,
        addon_id: str,
        command: Union[PAPICommand, PAPICommandGroup],
        parent_group: Optional[str] = None,
    ) -> None:
        """
        Register a command or command group for an addon.

        Args:
            addon_id: The ID of the addon registering the command
            command: The command or command group to register
            parent_group: Optional name of parent command group
        """
        if command.name is None:
            raise ValueError("Command must have a name")

        command.set_addon_id(addon_id)
        if parent_group:
            parent = self._commands[addon_id].get(parent_group)
            if not isinstance(parent, PAPICommandGroup):
                raise ValueError(
                    f"Parent group '{parent_group}' not found for addon {addon_id}"
                )
            parent.add_command(command)
        else:
            self._commands[addon_id][command.name] = command

    def create_cli(self) -> click.Group:
        """
        Create the complete CLI by combining all registered commands.

        Returns:
            The root command group containing all commands
        """
        if not self._root_group:
            self._root_group = PAPICommandGroup(
                name="papi", help="pAPI CLI tool for managing the system", commands={}
            )

            # Add built-in commands at initialization
            # These are imported at runtime to avoid circular imports
            @self._root_group.command()
            def webserver():
                """Start the production FastAPI web server."""
                from papi.papi_cli import webserver as ws

                return ws()

            @self._root_group.command()
            def shell():
                """Launch an interactive Python shell."""
                from papi.papi_cli import shell as sh

                return sh()

            @self._root_group.command()
            def mcpserver():
                """Start the standalone MCP server."""
                from papi.papi_cli import mcpserver as mcp

                return mcp()

        # Add all registered addon commands to root group
        for addon_id, commands in self._commands.items():
            for cmd in commands.values():
                if cmd.name is None or cmd.name in self._root_group.commands:
                    continue
                self._root_group.add_command(cmd)

        return self._root_group

    def get_commands_for_addon(
        self, addon_id: str
    ) -> List[Union[PAPICommand, PAPICommandGroup]]:
        """Get all commands registered for a specific addon."""
        return list(self._commands[addon_id].values())

    def clear(self) -> None:
        """Clear all registered commands. Mainly useful for testing."""
        self._initialize()
