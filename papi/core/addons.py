"""
Addon management system for dynamic module loading, dependency resolution,
model discovery, and router registration for FastAPI and custom protocols.
"""

import importlib
import os
import sys
from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from inspect import isclass, ismodule
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Type

from beanie import Document
from fastapi import APIRouter as FASTApiRouter
from loguru import logger
from sqlalchemy.orm import DeclarativeMeta

from papi.core.models.addons import AddonManifest
from papi.core.router import MPCRouter, RESTRouter


class AddonSetupHook:
    """
    Optional base class for addons that need to hook into the system lifecycle.
    Subclasses may override any of the following methods.
    """

    async def run(self) -> None:
        """Executed once during addon registration or initialization."""
        pass

    async def startup(self) -> None:
        """Executed during startup event."""
        pass

    async def shutdown(self) -> None:
        """Executed during shutdown event."""
        pass


class AddonsGraph:
    """
    Represents a directed acyclic graph (DAG) of addon dependencies.
    Provides functionality to add addons with their dependencies,
    detect circular dependencies, and obtain a topological order.
    """

    def __init__(self) -> None:
        """
        Initializes the AddonsGraph.
        - self.addons: maps addon_id to AddonManifest
        - self.dependencies: maps addon_id to set of dependent addon_ids
        - self.required_python_dependencies: set of all Python dependencies from addons
        """
        self.addons: Dict[str, AddonManifest] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.required_python_dependencies: Set[str] = set()
        logger.debug("AddonsGraph initialized")

    def add_module(self, addon: AddonManifest) -> None:
        """
        Adds a single addon to the graph without its dependencies.
        If the addon is already present, it is skipped.

        Args:
            addon (AddonManifest): The addon manifest to add.
        """
        addon_id = addon.addon_id
        if addon_id in self.addons:
            logger.debug(f"Addon '{addon_id}' already added, skipping")
            return

        self.addons[addon_id] = addon
        self.dependencies[addon_id].update(addon.dependencies)
        for dep in addon.dependencies:
            # Ensure all nodes exist in dependencies dictionary
            if dep not in self.dependencies:
                self.dependencies[dep] = set()

        self.required_python_dependencies.update(addon.python_dependencies)
        logger.debug(
            f"Added addon '{addon_id}' with dependencies: {addon.dependencies}"
        )

    def add_with_dependencies(
        self,
        addon: AddonManifest,
        all_manifests: Dict[str, AddonManifest],
        visited: Optional[Set[str]] = None,
    ) -> None:
        """
        Recursively adds the given addon and all its dependencies to the graph.
        Detects circular dependencies and raises RuntimeError if any are found.

        Args:
            addon (AddonManifest): The addon manifest to add.
            all_manifests (Dict[str, AddonManifest]): All available addon manifests.
            visited (Optional[Set[str]]): Set of currently visited addon IDs during recursion.

        Raises:
            RuntimeError: If a circular dependency or missing dependency is detected.
        """
        if visited is None:
            visited = set()
        failed = False

        addon_id = addon.addon_id
        if addon_id in visited:
            path = " -> ".join(list(visited) + [addon_id])
            logger.error(f"Circular dependency detected: {path}")
            raise RuntimeError(f"Circular dependency detected in path: {path}")

        if addon_id in self.addons:
            logger.debug(f"Addon '{addon_id}' already processed, skipping recursion")
            return

        logger.debug(
            f"Processing addon '{addon_id}' with dependencies {addon.dependencies}"
        )
        visited.add(addon_id)

        for dep_id in addon.dependencies:
            dep_manifest = all_manifests.get(dep_id)
            if not dep_manifest:
                logger.error(
                    f"Dependency '{dep_id}' of addon '{addon_id}' not found, skipping {addon_id}"
                )
                failed = True
                continue
            self.add_with_dependencies(dep_manifest, all_manifests, visited)

        visited.remove(addon_id)
        if not failed:
            self.add_module(addon)
            logger.debug(f"Finished processing addon '{addon_id}'")
        logger.debug(f"Finished processing addon '{addon_id}  with errors'")

    def topological_order(self) -> List[str]:
        """
        Computes and returns a topological order of the addons
        based on their dependencies.

        Returns:
            List[str]: Addon IDs in topological order.

        Raises:
            RuntimeError: If a circular dependency is detected.
        """
        ts = TopologicalSorter(self.dependencies)
        try:
            order = list(ts.static_order())
            logger.debug(f"Topological order computed: {order}")
            return order
        except CycleError as e:
            logger.error(
                f"Circular dependency detected during topological sort: {e.args}"
            )
            raise RuntimeError(f"Circular dependency detected: {e.args}")

    def get_all_python_dependencies(self) -> List[str]:
        """
        Returns a sorted list of all unique Python package dependencies
        required by the addons.

        Returns:
            List[str]: Sorted list of Python dependencies.
        """
        deps = sorted(self.required_python_dependencies)
        logger.debug(f"Collected Python dependencies: {deps}")
        return deps

    def __str__(self) -> str:
        """
        Returns a human-readable string representing the dependency graph.

        Returns:
            str: Multi-line string with addon dependencies.
        """
        return "\n".join(
            f"{addon} -> {sorted(deps)}" for addon, deps in self.dependencies.items()
        )


def get_addons_from_dir(addons_path: str, enabled_addons_ids: List[str]) -> AddonsGraph:
    """
    Loads all addon manifests from the given directory and builds an AddonsGraph
    containing the enabled addons and all their recursive dependencies.

    Args:
        addons_path (str): Path to the directory containing addon subdirectories.
        enabled_addons_ids (List[str]): List of addon IDs to enable.

    Returns:
        AddonsGraph: The constructed graph of enabled addons and dependencies.

    Raises:
        RuntimeError: If the addons directory is not found, if an enabled addon
                      manifest is missing, or if circular/missing dependencies occur.
    """
    base_path = Path(addons_path).resolve()
    logger.debug(f"Resolving addons directory: {base_path}")
    if not base_path.is_dir():
        logger.error(f"Addons directory not found: {base_path}")
        raise RuntimeError(f"Addons directory not found: {base_path}")

    # Load all manifests from directory
    all_manifests: Dict[str, AddonManifest] = {}
    for entry in os.scandir(base_path):
        if entry.is_dir():
            manifest_path = base_path / entry.name / "manifest.yaml"
            if manifest_path.exists():
                try:
                    manifest = AddonManifest.from_yaml(manifest_path)
                    all_manifests[manifest.addon_id] = manifest
                    logger.debug(f"Loaded manifest for addon '{manifest.addon_id}'")
                except Exception as e:
                    logger.error(f"Failed to load manifest {manifest_path}: {e}")

    graph = AddonsGraph()

    # Add enabled addons and their recursive dependencies
    for addon_id in enabled_addons_ids:
        manifest = all_manifests.get(addon_id)
        if not manifest:
            logger.error(f"Enabled addon '{addon_id}' not found in manifests")
            raise RuntimeError(f"Enabled addon '{addon_id}' not found")
        logger.debug(f"Adding enabled addon '{addon_id}' and its dependencies")
        graph.add_with_dependencies(manifest, all_manifests)

    logger.info(f"Finished building AddonsGraph with {len(graph.addons)} addons")
    return graph


def import_addon_module(addon: AddonManifest) -> ModuleType:
    """
    Dynamically import an addon Python module given its manifest.
    """
    package_path = str(addon.path.parent)
    module_name = addon.path.name

    sys.path.insert(0, package_path)
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        raise ImportError(f"Error loading addon '{addon.addon_id}': {e}") from e
    finally:
        sys.path.remove(package_path)


def load_and_import_all_addons(graph: AddonsGraph) -> Dict[str, ModuleType]:
    """
    Load and import all addons from the graph in correct dependency order.
    Returns a dictionary of {addon_id: imported_module}.
    """
    modules: Dict[str, ModuleType] = {}

    for addon_id in graph.topological_order():
        addon = graph.addons[addon_id]
        modules[addon_id] = import_addon_module(addon)

    return modules


def get_beanie_documents_from_addon(module: ModuleType) -> List[Type[Document]]:
    """
    Recursively search an addon module and return all Beanie document classes.
    """
    models: Set[Type[Document]] = set()
    processed: Set[ModuleType] = set()

    def _search(current: ModuleType) -> None:
        if current in processed:
            return
        processed.add(current)

        for attr_name in dir(current):
            if attr_name.startswith("_"):
                continue
            attr = getattr(current, attr_name)
            if _is_document_subclass(attr):
                models.add(attr)
            elif _is_submodule(attr, module):
                _search(attr)

    _search(module)
    return list(models)


def get_sqlalchemy_models_from_addon(module: ModuleType) -> List[Type[DeclarativeMeta]]:
    """
    Recursively search an addon module and return all SQLAlchemy declarative model classes.
    """
    models: Set[Type[DeclarativeMeta]] = set()
    processed: Set[ModuleType] = set()

    def _search(current: ModuleType) -> None:
        if current in processed:
            return
        processed.add(current)

        for attr_name in dir(current):
            if attr_name.startswith("_"):
                continue
            attr = getattr(current, attr_name)
            if _is_sqlalchemy_model(attr):
                models.add(attr)
            elif _is_submodule(attr, module):
                _search(attr)

    _search(module)
    return list(models)


def get_addon_setup_hooks(module: ModuleType) -> List[Type[AddonSetupHook]]:
    hooks: Set[Type[AddonSetupHook]] = set()
    processed: Set[ModuleType] = set()

    def _search(current: ModuleType) -> None:
        if current in processed:
            return
        processed.add(current)

        for attr_name in dir(current):
            if attr_name.startswith("_"):
                continue
            attr = getattr(current, attr_name)
            if _implements_addon_setup_hook(attr):
                hooks.add(attr)
            elif _is_submodule(attr, module):
                _search(attr)

    _search(module)
    return list(hooks)


def get_router_from_addon(
    module: ModuleType,
) -> List[RESTRouter | MPCRouter | FASTApiRouter]:
    """
    Recursively search an addon module and return all router instances
    (REST, MPC, or FastAPI).
    """
    routers = []
    processed = set()

    def _search(current: ModuleType) -> None:
        if current in processed:
            return
        processed.add(current)

        for attr_name in dir(current):
            if attr_name.startswith("_"):
                continue
            attr = getattr(current, attr_name)
            if isinstance(attr, (RESTRouter, MPCRouter, FASTApiRouter)):
                routers.append(attr)
            elif _is_submodule(attr, module):
                _search(attr)

    _search(module)
    return routers


def has_static_files(module: ModuleType) -> bool:
    """
    Check if the addon module contains a 'static' directory.
    """
    return (Path(module.__path__[0]) / "static").exists()


def _is_document_subclass(obj: Any) -> bool:
    """
    Return True if the object is a Beanie document subclass.
    """
    return isclass(obj) and issubclass(obj, Document) and obj is not Document


def _is_sqlalchemy_model(obj: Any) -> bool:
    """
    Return True if the object is a SQLAlchemy declarative model class.
    """
    return isclass(obj) and hasattr(obj, "__tablename__") and hasattr(obj, "__table__")


def _is_submodule(obj: Any, parent: ModuleType) -> bool:
    """
    Return True if the object is a submodule of the given parent module.
    """
    return (
        ismodule(obj)
        and obj.__package__ is not None
        and obj.__package__.startswith(parent.__package__)
    )


def _implements_addon_setup_hook(obj: object) -> bool:
    """
    Check if the object is a class or instance that implements AddonSetupHook.
    """
    # Si es una clase, verificamos con issubclass, si es instancia, con isinstance
    if isinstance(obj, type):
        # issubclass puede lanzar TypeError si obj no es clase, pero ya chequeamos que sí
        return issubclass(obj, AddonSetupHook)
    return isinstance(obj, AddonSetupHook)
