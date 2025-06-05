"""
Addon management system for dynamic module loading, dependency resolution,
model discovery, and router registration for FastAPI and custom protocols.
"""

import importlib
import pkgutil
import sys
from collections import defaultdict
from inspect import isclass, ismodule
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Set, Type

from beanie import Document
from fastapi import APIRouter as FASTApiRouter
from loguru import logger
from sqlalchemy.orm import DeclarativeMeta

from papi.core.models.addons import AddonManifest
from papi.core.router import MPCRouter, RESTRouter


class AddonSetupHook:
    """
    Optional interface for addons that need to run setup logic before system start.
    Can be used for tasks such as migrations, initial configuration, or checks.
    """

    async def run(self) -> None:
        """Executed when the addon is registered or initialized."""
        pass


class AddonsGraph:
    """
    Represents a directed acyclic graph (DAG) of addon dependencies.
    Provides cycle detection and topological sorting for load order resolution.
    """

    def __init__(self) -> None:
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.addons: Dict[str, AddonManifest] = {}
        self.required_python_dependencies: Set[str] = set()

    def add_module(self, addon_definition: AddonManifest) -> None:
        """
        Register a new addon and its dependencies in the graph.
        """
        addon_id = addon_definition.addon_id
        if addon_id in self.addons:
            raise ValueError(f"Addon '{addon_definition.name}' is already registered")

        self.addons[addon_id] = addon_definition
        self.graph[addon_id].extend(addon_definition.dependencies)

        for dependency in addon_definition.dependencies:
            self.graph[dependency]

        self.required_python_dependencies.update(addon_definition.python_dependencies)

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect cycles in the dependency graph.
        Returns a list of cycles found (each as a list of addon IDs).
        """
        visited: Set[str] = set()
        stack: Set[str] = set()
        current_path: List[str] = []
        cycles: List[List[str]] = []

        def dfs(node: str) -> None:
            visited.add(node)
            stack.add(node)
            current_path.append(node)

            for neighbor in self.graph[node]:
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in stack:
                    cycle_start = current_path.index(neighbor)
                    cycles.append(current_path[cycle_start:] + [neighbor])

            stack.remove(node)
            current_path.pop()

        for node in self.graph:
            if node not in visited:
                dfs(node)

        return cycles

    def topological_order(self) -> List[str]:
        """
        Returns a list of addon IDs in topological order of dependencies.
        Raises an exception if cycles are detected.
        """
        if cycles := self.detect_cycles():
            raise ValueError(f"Dependency cycle detected: {cycles}")

        visited: Set[str] = set()
        order: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            for neighbor in self.graph[node]:
                if neighbor not in visited:
                    dfs(neighbor)
            order.append(node)

        for node in self.graph:
            if node not in visited:
                dfs(node)

        return order

    def get_all_python_dependencies(self) -> List[str]:
        return sorted(self.required_python_dependencies)

    def __str__(self) -> str:
        return "\n".join(f"{source} -> {deps}" for source, deps in self.graph.items())


def get_addons_from_dirs(
    addons_paths: List[str], enabled_addons_ids: List[str]
) -> AddonsGraph:
    """
    Scan directories for available addons, parse their manifests, and build
    a dependency graph including implicit dependencies.
    """
    graph = AddonsGraph()
    detected_dependencies: Set[str] = set()
    addons_map: Dict[str, AddonManifest] = {}

    for addons_path in addons_paths:
        base_path = Path(addons_path).resolve()

        if not base_path.is_dir():
            logger.warning(f"Extra addons directory not found in: {base_path}")

        sys.path.insert(0, str(base_path))
        try:
            for module_info in pkgutil.iter_modules([str(base_path)]):
                package_path = base_path / module_info.name
                manifest_path = package_path / "manifest.yaml"

                if not manifest_path.exists():
                    raise FileNotFoundError(
                        f"Missing 'manifest.yaml' in addon: {module_info.name}"
                    )

                manifest = AddonManifest.from_yaml(manifest_path)
                addons_map[module_info.name] = manifest
                detected_dependencies.update(manifest.dependencies)

                if module_info.ispkg and (
                    module_info.name in enabled_addons_ids
                    or module_info.name in detected_dependencies
                ):
                    graph.add_module(manifest)
        finally:
            sys.path.pop(0)

    for addon, manifest in addons_map.items():
        if addon in detected_dependencies and addon not in graph.addons:
            graph.add_module(manifest)

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
