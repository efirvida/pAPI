"""
Base classes for the pAPI CLI system.

This module provides the base classes that addons will use to define their CLI commands.
Commands and groups inherit from Click's Command and Group classes to maintain
compatibility while adding pAPI-specific functionality.
"""

from typing import Any, Callable, Optional

import click
from click_default_group import DefaultGroup


class PAPICommand(click.Command):
    """Base class for pAPI CLI commands."""

    def __init__(self, name: Optional[str] = None, **attrs: Any) -> None:
        if name is None and "callback" in attrs:
            name = attrs["callback"].__name__
        super().__init__(name=name, **attrs)
        self.addon_id: Optional[str] = None

    def set_addon_id(self, addon_id: str) -> None:
        """Set the ID of the addon that owns this command."""
        self.addon_id = addon_id


class PAPICommandGroup(DefaultGroup):
    """Base class for pAPI CLI command groups."""

    def __init__(
        self,
        name: Optional[str] = None,
        commands: Optional[dict[str, PAPICommand]] = None,
        **attrs: Any,
    ) -> None:
        super().__init__(name=name, **attrs)
        # Initialize commands dict safely
        if commands:
            for cmd_name, cmd in commands.items():
                self.add_command(cmd, cmd_name)
        self.addon_id: Optional[str] = None

    def set_addon_id(self, addon_id: str) -> None:
        """Set the ID of the addon that owns this command group."""
        self.addon_id = addon_id
        for cmd in self.commands.values():
            if isinstance(cmd, (PAPICommand, PAPICommandGroup)):
                cmd.set_addon_id(addon_id)

    def command(self, *args: Any, **kwargs: Any) -> Callable[..., click.Command]:
        """Decorator to create a new PAPICommand."""
        # Set default command class if not specified
        kwargs.setdefault("cls", PAPICommand)
        # Get the parent class's command decorator
        parent_decorator = super(PAPICommandGroup, self).command(*args, **kwargs)

        def decorator(f: Callable[..., Any]) -> click.Command:
            cmd = parent_decorator(f)
            if isinstance(cmd, PAPICommand) and self.addon_id:
                cmd.set_addon_id(self.addon_id)
            return cmd

        return decorator

    def group(self, *args: Any, **kwargs: Any) -> Callable[..., click.Group]:
        """Decorator to create a new PAPICommandGroup."""
        kwargs.setdefault("cls", PAPICommandGroup)
        parent_decorator = super(PAPICommandGroup, self).group(*args, **kwargs)

        def decorator(f: Callable[..., Any]) -> click.Group:
            grp = parent_decorator(f)
            if isinstance(grp, PAPICommandGroup) and self.addon_id:
                grp.set_addon_id(self.addon_id)
            return grp

        return decorator
