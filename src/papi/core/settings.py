from functools import lru_cache
from pathlib import Path

import yaml
from core.models.config import AppConfig


def load_config(path: Path) -> AppConfig:
    with path.open("r") as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)


@lru_cache()
def get_config() -> AppConfig:
    config_path = Path("config.yaml")
    return load_config(config_path)
