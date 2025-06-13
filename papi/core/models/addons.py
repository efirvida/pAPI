from pathlib import Path
from typing import List, Optional, Sequence

import yaml
from pydantic import BaseModel, Field


class AddonManifest(BaseModel):
    """
    Model representing the manifest file of a pAPI addon.

    This model is used to load and validate the configuration defined in a YAML file for a specific addon.

    Attributes:
        name (str): The internal name of the addon (derived from the directory name).
        title (Optional[str]): Human-readable title of the addon. Defaults to "pAPI Addon".
        version (Optional[str]): Version number of the addon. Defaults to "0.1".
        dependencies (List[str]): List of required addon identifiers this addon depends on.
        python_dependencies (List[str]): List of Python package dependencies required by the addon.
        authors (Union[str, Sequence[str], None]): Author name or list of authors.
        description (Optional[str]): Optional addon description.
        path (Path): Filesystem path to the addon directory (excluded from serialization).

    Properties:
        addon_id (str): The unique ID of the addon, derived from the folder name.

    Class Methods:
        from_yaml(path: Path) -> AddonManifest:
            Load an addon manifest from a YAML file.

    Example:
        ```python
        from pathlib import Path

        manifest = AddonManifest.from_yaml(Path("addons/image_storage/manifest.yaml"))
        print(manifest.title)  # "pAPI Addon" or custom title
        print(manifest.addon_id)  # "image_storage"
        ```
    """

    name: str
    title: str | None = "pAPI Addon"
    version: str | None = "0.1"
    dependencies: List[str] = Field(default_factory=list)
    python_dependencies: List[str] = Field(default_factory=list)
    authors: str | Sequence | None = None
    description: Optional[str] = None
    path: Path = Field(exclude=True)

    @property
    def addon_id(self) -> str:
        return self.path.parts[-1]

    @classmethod
    def from_yaml(cls, path: Path):
        """
        Load an `AddonManifest` from a YAML file.

        Args:
            path (Path): Path to the `manifest.yaml` file.

        Returns:
            AddonManifest: An instance of the manifest model populated with data from the file.

        Raises:
            yaml.YAMLError: If the YAML is invalid or cannot be parsed.

        Example:
            Example `manifest.yaml` content:

            ```yaml
            name: custom addon
            version: 0.0.1
            description: My Custom API
            author: My Self

            dependencies:
            - user_auth_system

            python_dependencies:
            - "requests>=2.28.0"
            ```

            Usage:

            ```python
            from pathlib import Path
            manifest = AddonManifest.from_yaml(Path("addons/custom_addon/manifest.yaml"))
            print(manifest.addon_id)  # custom_addon
            print(manifest.name)  # custom_addon
            print(manifest.version)  # 0.1
            print(manifest.dependencies)  # ['user_auth_system']
            print(manifest.python_dependencies)  # ['requests>=2.28.0']
            ```
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        addon_dir = path.parent
        data["name"] = addon_dir.name

        return cls(**data, path=addon_dir)
