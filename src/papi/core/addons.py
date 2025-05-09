"""
Addon management system for dynamic module loading and dependency resolution.
"""

import importlib
import pkgutil
import sys
from collections import defaultdict
from inspect import isclass, ismodule
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Set, Tuple, Type

from beanie import Document

from papi.core.models.addons import AddonManifest
from papi.core.router import RESTRouter


class AddonsGraph:
    """
    Represents addon dependencies as a directed acyclic graph (DAG)
    and provides topological sorting with cycle detection.
    """

    def __init__(self) -> None:
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.addons: Dict[str, AddonManifest] = {}

    def add_module(self, addon_definition: AddonManifest) -> None:
        addon_id = addon_definition.addon_id
        if addon_id in self.addons:
            raise ValueError(f"Addon '{addon_definition.name}' is already registered")

        self.addons[addon_id] = addon_definition
        self.graph[addon_id].extend(addon_definition.depends)

        for dependency in addon_definition.depends:
            self.graph[dependency]  # Ensure node exists

    def detect_cycles(self) -> List[List[str]]:
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

        return order[::-1]

    def __str__(self) -> str:
        return "\n".join(f"{source} -> {deps}" for source, deps in self.graph.items())


def get_addons_from_dirs(
    addons_paths: Tuple[str], enabled_addons_ids: List[str]
) -> AddonsGraph:
    graph = AddonsGraph()
    detected_dependencies: Set[str] = set()
    addons_map: Dict[str, AddonManifest] = {}

    for addons_path in addons_paths:
        base_path = Path(addons_path).resolve()

        if not base_path.is_dir():
            raise FileNotFoundError(f"Addons directory not found: {base_path}")

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
                detected_dependencies.update(manifest.depends)

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
    modules: Dict[str, ModuleType] = {}

    for addon_id in graph.topological_order():
        addon = graph.addons[addon_id]
        modules[addon_id] = import_addon_module(addon)

    return modules


def get_beanie_documents_from_addon(module: ModuleType) -> List[Type[Document]]:
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


def get_router_from_addon(module: ModuleType) -> List[RESTRouter]:
    routers: List[RESTRouter] = []
    processed: Set[ModuleType] = set()

    def _search(current: ModuleType) -> None:
        if current in processed:
            return
        processed.add(current)

        for attr_name in dir(current):
            if attr_name.startswith("_"):
                continue
            attr = getattr(current, attr_name)
            if isinstance(attr, RESTRouter):
                routers.append(attr)
            elif _is_submodule(attr, module):
                _search(attr)

    _search(module)
    return routers


def has_static_files(module: ModuleType) -> bool:
    return (Path(module.__path__[0]) / "static").exists()


def _is_document_subclass(obj: Any) -> bool:
    return isclass(obj) and issubclass(obj, Document) and obj is not Document


def _is_submodule(obj: Any, parent: ModuleType) -> bool:
    return (
        ismodule(obj)
        and obj.__package__ is not None
        and obj.__package__.startswith(parent.__package__)
    )
