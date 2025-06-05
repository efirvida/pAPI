from pathlib import Path
from typing import List, Optional, Sequence

import yaml
from pydantic import BaseModel, Field


class AddonManifest(BaseModel):
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
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        addon_dir = path.parent
        data["name"] = addon_dir.name

        return cls(**data, path=addon_dir)
