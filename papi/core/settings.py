from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from papi.core.models.config import AppConfig

_config_cache: Optional[AppConfig] = None
_config_file_path: Optional[str] = None


def get_config(config_file_path: Optional[str] = None) -> AppConfig:
    """
    Load and cache the application configuration from a YAML file.

    Args:
        config_file_path (Optional[str]): Path to the configuration file.
            If not provided, uses cached path or defaults to 'config.yaml'.

    Returns:
        AppConfig: The loaded configuration object.

    Raises:
        FileNotFoundError: If the specified config file does not exist.
        yaml.YAMLError: If the file cannot be parsed as valid YAML.
        Exception: If the data cannot be converted into an AppConfig.
    """
    global _config_cache, _config_file_path

    logger.debug("=== get_config() called ===")
    logger.debug(f"Received config_file_path: {config_file_path}")
    logger.debug(f"Current cached _config_file_path: {_config_file_path}")
    logger.debug(f"Config cache status: {'filled' if _config_cache else 'empty'}")

    if _config_cache is not None and config_file_path is None:
        logger.debug("Returning cached configuration object.")
        return _config_cache

    # Determine the effective configuration file path
    if config_file_path:
        requested_path = Path(config_file_path).resolve()
        _config_file_path = str(requested_path)
    elif _config_file_path:
        requested_path = Path(_config_file_path).resolve()
    else:
        requested_path = Path("config.yaml").resolve()
        _config_file_path = str(requested_path)

    logger.info(f"Loading configuration file from: {requested_path}")

    if not requested_path.is_file():
        logger.error(f"Configuration file not found: {requested_path}")
        raise FileNotFoundError(f"Configuration file not found: {requested_path}")

    try:
        with requested_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _config_cache = AppConfig(**data)
        logger.debug("Configuration file successfully parsed and cached.")
    except yaml.YAMLError:
        logger.exception("Failed to parse YAML configuration file.")
        raise
    except Exception:
        logger.exception("Failed to load configuration into AppConfig.")
        raise

    return _config_cache
