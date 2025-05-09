from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class AddonManifest(BaseModel):
    name: str
    version: Optional[str] = "0.1"
    depends: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    description: Optional[str] = None
    path: Path = Field(exclude=True)

    @property
    def addon_id(self) -> str:
        return self.path.parts[-1]

    @classmethod
    def from_yaml(cls, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data, path=path.parent)
