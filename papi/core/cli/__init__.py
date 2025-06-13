"""
pAPI CLI System.

This package provides a modular CLI system that allows addons to dynamically
register their own commands. The main components are:
- PAPICommand/PAPICommandGroup: Base classes for CLI commands
- CLIRegistry: Central registry for managing commands
"""

from .base import PAPICommand, PAPICommandGroup
from .registry import CLIRegistry

__all__ = ['PAPICommand', 'PAPICommandGroup', 'CLIRegistry']