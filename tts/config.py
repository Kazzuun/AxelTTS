import tomllib
from pathlib import Path

from tts.logger_config import logger
from tts.models import Config


def load_config() -> Config:
    config_path = Path("config.toml")
    default_config_path = Path("default_config.toml")

    logger.info(f"Loading config file from {config_path.name}...")

    if not config_path.exists():
        logger.warning(
            f"Custom config at {config_path.name} doesn't exist... Using default config at {default_config_path.name}"
        )
        config = _load_config_file(default_config_path)
    else:
        config = _load_config_file(config_path)

    return config


def _load_config_file(path: Path) -> Config:
    with path.open("rb") as f:
        toml_config = tomllib.load(f)
    config = Config(**toml_config["app"], **toml_config["tts"])
    return config
