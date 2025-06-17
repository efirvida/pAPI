"""
CLI Registry for pAPI.

This module provides the central registry for CLI commands, allowing addons to
register their commands dynamically. The registry manages command namespacing
and ensures commands from different addons don't conflict.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Union

from papi.core.cli.base import PAPICommand, PAPICommandGroup


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

    def get_commands_for_addon(
        self, addon_id: str
    ) -> List[Union[PAPICommand, PAPICommandGroup]]:
        """Get all commands registered for a specific addon."""
        return list(self._commands[addon_id].values())

    def get_all_registered_commands(self) -> List[Union[PAPICommand, PAPICommandGroup]]:
        """Returns a flat list of all registered commands from all addons."""
        all_commands = []
        for commands in self._commands.values():
            all_commands.extend(commands.values())
        return all_commands

    def clear(self) -> None:
        """Clear all registered commands. Mainly useful for testing."""
        self._initialize()


registry = CLIRegistry()
