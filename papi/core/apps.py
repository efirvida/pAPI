"""
App management system for dynamic module loading, dependency resolution,
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

from papi.core.models.apps import AppManifest
from papi.core.router import MPCRouter, RESTRouter


class AppSetupHook:
    """
    Optional base class for apps that need to hook into the system lifecycle.
    Subclasses may override any of the following methods.
    """

    async def startup(self) -> None:
        """Executed during startup event."""
        pass

    async def shutdown(self) -> None:
        """Executed during shutdown event."""
        pass


class AppsGraph:
    """
    Represents a directed acyclic graph (DAG) of app dependencies.
    Provides functionality to add apps with their dependencies,
    detect circular dependencies, and obtain a topological order.
    """

    def __init__(self) -> None:
        """
        Initializes the AppsGraph.
        - self.apps: maps app_id to AppManifest
        - self.dependencies: maps app_id to set of dependent app_ids
        - self.required_python_dependencies: set of all Python dependencies from apps
        """
        self.apps: Dict[str, AppManifest] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.required_python_dependencies: Set[str] = set()
        logger.debug("AppsGraph initialized")

    def add_module(self, app: AppManifest) -> None:
        """
        Adds a single app to the graph without its dependencies.
        If the app is already present, it is skipped.

        Args:
            app (AppManifest): The app manifest to add.
        """
        app_id = app.app_id
        if app_id in self.apps:
            logger.debug(f"App '{app_id}' already added, skipping")
            return

        self.apps[app_id] = app
        # Initialize dependencies entry if it doesn't exist
        if app_id not in self.dependencies:
            self.dependencies[app_id] = set()
        self.dependencies[app_id].update(app.dependencies)
        for dep in app.dependencies:
            # Ensure all nodes exist in dependencies dictionary
            if dep not in self.dependencies:
                self.dependencies[dep] = set()

        self.required_python_dependencies.update(app.python_dependencies)
        logger.debug(
            f"Added app '{app_id}' with dependencies: {app.dependencies}"
        )

    def add_with_dependencies(
        self,
        app: AppManifest,
        all_manifests: Dict[str, AppManifest],
        visited: Optional[Set[str]] = None,
    ) -> None:
        """
        Recursively adds the given app and all its dependencies to the graph.
        Detects circular dependencies and raises RuntimeError if any are found.

        Args:
            app (AppManifest): The app manifest to add.
            all_manifests (Dict[str, AppManifest]): All available app manifests.
            visited (Optional[Set[str]]): Set of currently visited app IDs during recursion.

        Raises:
            RuntimeError: If a circular dependency or missing dependency is detected.
        """
        if visited is None:
            visited = set()
        failed = False

        app_id = app.app_id
        if app_id in visited:
            path = " -> ".join(list(visited) + [app_id])
            logger.error(f"Circular dependency detected: {path}")
            raise RuntimeError(f"Circular dependency detected in path: {path}")

        if app_id in self.apps:
            logger.debug(f"App '{app_id}' already processed, skipping recursion")
            return

        logger.debug(
            f"Processing app '{app_id}' with dependencies {app.dependencies}"
        )
        visited.add(app_id)

        for dep_id in app.dependencies:
            dep_manifest = all_manifests.get(dep_id)
            if not dep_manifest:
                logger.error(
                    f"Dependency '{dep_id}' of app '{app_id}' not found, skipping {app_id}"
                )
                failed = True
                continue
            self.add_with_dependencies(dep_manifest, all_manifests, visited)

        visited.remove(app_id)
        if not failed:
            self.add_module(app)
            logger.debug(f"Finished processing app '{app_id}'")
        else:
            logger.debug(f"Finished processing app '{app_id}' with errors")

    def topological_order(self) -> List[str]:
        """
        Computes and returns a topological order of the apps
        based on their dependencies.

        Returns:
            List[str]: App IDs in topological order.

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
        required by the apps.

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
            str: Multi-line string with app dependencies.
        """
        return "\n".join(
            f"{app} -> {sorted(deps)}" for app, deps in self.dependencies.items()
        )


def get_apps_from_dir(apps_path: str, enabled_apps_ids: List[str]) -> AppsGraph:
    """
    Loads all app manifests from the given directory and builds an AppsGraph
    containing the enabled apps and all their recursive dependencies.

    Args:
        apps_path (str): Path to the directory containing app subdirectories.
        enabled_apps_ids (List[str]): List of app IDs to enable.

    Returns:
        AppsGraph: The constructed graph of enabled apps and dependencies.

    Raises:
        RuntimeError: If the apps directory is not found, if an enabled app
                      manifest is missing, or if circular/missing dependencies occur.
    """
    base_path = Path(apps_path).resolve()
    logger.debug(f"Resolving apps directory: {base_path}")
    if not base_path.is_dir():
        logger.error(f"Apps directory not found: {base_path}")
        raise RuntimeError(f"Apps directory not found: {base_path}")

    # Load all manifests from directory
    all_manifests: Dict[str, AppManifest] = {}
    for entry in os.scandir(base_path):
        if entry.is_dir():
            manifest_path = base_path / entry.name / "manifest.yaml"
            if manifest_path.exists():
                try:
                    manifest = AppManifest.from_yaml(manifest_path)
                    all_manifests[manifest.app_id] = manifest
                    logger.debug(f"Loaded manifest for app '{manifest.app_id}'")
                except Exception as e:
                    logger.error(f"Failed to load manifest {manifest_path}: {e}")

    graph = AppsGraph()

    # Add enabled apps and their recursive dependencies
    for app_id in enabled_apps_ids:
        manifest = all_manifests.get(app_id)
        if not manifest:
            logger.error(f"Enabled app '{app_id}' not found in manifests")
            raise RuntimeError(f"Enabled app '{app_id}' not found")
        logger.debug(f"Adding enabled app '{app_id}' and its dependencies")
        graph.add_with_dependencies(manifest, all_manifests)

    logger.info(f"Finished building AppsGraph with {len(graph.apps)} apps")
    return graph


def import_app_module(app: AppManifest) -> ModuleType:
    """
    Dynamically import an app Python module given its manifest.
    """
    package_path = str(app.path.parent)
    module_name = app.path.name

    sys.path.insert(0, package_path)
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        raise ImportError(f"Error loading app '{app.app_id}': {e}") from e
    finally:
        sys.path.remove(package_path)


def load_and_import_all_apps(graph: AppsGraph) -> Dict[str, ModuleType]:
    """
    Load and import all apps from the graph in correct dependency order.
    Returns a dictionary of {app_id: imported_module}.
    """
    modules: Dict[str, ModuleType] = {}

    for app_id in graph.topological_order():
        app = graph.apps[app_id]
        modules[app_id] = import_app_module(app)

    return modules


def get_beanie_documents_from_app(module: ModuleType) -> List[Type[Document]]:
    """
    Recursively search an app module and return all Beanie document classes.
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


def get_sqlalchemy_models_from_app(module: ModuleType) -> List[Type[DeclarativeMeta]]:
    """
    Recursively search an app module and return all SQLAlchemy declarative model classes.
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


def get_app_setup_hooks(module: ModuleType) -> List[Type[AppSetupHook]]:
    hooks: Set[Type[AppSetupHook]] = set()
    processed: Set[ModuleType] = set()

    def _search(current: ModuleType) -> None:
        if current in processed:
            return
        processed.add(current)

        for attr_name in dir(current):
            if attr_name.startswith("_"):
                continue
            attr = getattr(current, attr_name)
            if _implements_app_setup_hook(attr):
                hooks.add(attr)
            elif _is_submodule(attr, module):
                _search(attr)

    _search(module)
    return list(hooks)


def get_router_from_app(
    module: ModuleType,
) -> List[RESTRouter | MPCRouter | FASTApiRouter]:
    """
    Recursively search an app module and return all router instances
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
    Check if the app module contains a 'static' directory.
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


def _implements_app_setup_hook(obj: object) -> bool:
    """
    Check if the object is a class or instance that implements AppSetupHook.
    """
    # Si es una clase, verificamos con issubclass, si es instancia, con isinstance
    if isinstance(obj, type):
        # issubclass puede lanzar TypeError si obj no es clase, pero ya chequeamos que sí
        return issubclass(obj, AppSetupHook)
    return isinstance(obj, AppSetupHook)
