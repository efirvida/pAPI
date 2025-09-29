from pathlib import Path
from typing import List, Optional, Sequence

import yaml
from pydantic import BaseModel, Field


class AppManifest(BaseModel):
    """
    Model representing the manifest file of a pAPI app.

    This model is used to load and validate the configuration defined in a YAML file for a specific app.

    Attributes:
        name (str): The internal name of the app (derived from the directory name).
        title (Optional[str]): Human-readable title of the app. Defaults to "pAPI App".
        version (Optional[str]): Version number of the app. Defaults to "0.1".
        dependencies (List[str]): List of required app identifiers this app depends on.
        python_dependencies (List[str]): List of Python package dependencies required by the app.
        authors (Union[str, Sequence[str], None]): Author name or list of authors.
        description (Optional[str]): Optional app description.
        path (Path): Filesystem path to the app directory (excluded from serialization).

    Properties:
        app_id (str): The unique ID of the app, derived from the folder name.

    Class Methods:
        from_yaml(path: Path) -> AppManifest:
            Load an app manifest from a YAML file.

    Example:
        ```python
        from pathlib import Path

        manifest = AppManifest.from_yaml(Path("apps/image_storage/manifest.yaml"))
        print(manifest.title)  # "pAPI App" or custom title
        print(manifest.app_id)  # "image_storage"
        ```
    """

    name: str
    title: str | None = "pAPI App"
    version: str | None = "0.1"
    dependencies: List[str] = Field(default_factory=list)
    python_dependencies: List[str] = Field(default_factory=list)
    authors: str | Sequence | None = None
    description: Optional[str] = None
    path: Path = Field(exclude=True)

    @property
    def app_id(self) -> str:
        return self.path.parts[-1]

    @classmethod
    def from_yaml(cls, path: Path):
        """
        Load an `AppManifest` from a YAML file.

        Args:
            path (Path): Path to the `manifest.yaml` file.

        Returns:
            AppManifest: An instance of the manifest model populated with data from the file.

        Raises:
            yaml.YAMLError: If the YAML is invalid or cannot be parsed.

        Example:
            Example `manifest.yaml` content:

            ```yaml
            name: custom app
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
            manifest = AppManifest.from_yaml(Path("apps/custom_app/manifest.yaml"))
            print(manifest.app_id)  # custom_app
            print(manifest.name)  # custom_app
            print(manifest.version)  # 0.1
            print(manifest.dependencies)  # ['user_auth_system']
            print(manifest.python_dependencies)  # ['requests>=2.28.0']
            ```
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        app_dir = path.parent
        data["name"] = app_dir.name

        return cls(**data, path=app_dir)
