import yaml

from papi.core.models.config import AppConfig

_config_cache: AppConfig | None = None


def get_config(config_file_path: str | None = None) -> AppConfig:
    """
    Load and return the application configuration as a cached singleton.

    This function reads a YAML configuration file and returns an instance of `AppConfig`.
    It uses an internal cache to avoid reloading and reparsing the file on subsequent calls.

    If no file path is provided, it defaults to `"config.yaml"` in the current working directory.

    Args:
        config_file_path (str | None): Path to the YAML configuration file.
            If None, defaults to `"config.yaml"`.

    Returns:
        AppConfig: The parsed application configuration.

    Raises:
        FileNotFoundError: If the specified config file does not exist.
        yaml.YAMLError: If the YAML content cannot be parsed.
        TypeError: If the content does not match the `AppConfig` schema.
    """
    global _config_cache

    if _config_cache is None:
        if config_file_path is None:
            config_file_path = "config.yaml"

        with open(config_file_path, "r") as f:
            data = yaml.safe_load(f)
            _config_cache = AppConfig(**data)

    return _config_cache
