import tomllib
from pathlib import Path

from tts.models import Config

DEFAULT_CONFIG_PATH = Path("default_config.toml")
CONFIG_PATH = Path("config.toml")


def load_config() -> Config:
    config = _load_config_file(DEFAULT_CONFIG_PATH) if not CONFIG_PATH.is_file() else _load_config_file(CONFIG_PATH)
    return config


def _load_config_file(path: Path) -> Config:
    with path.open("rb") as f:
        toml_config = tomllib.load(f)

    top_level_keys = ["app", "tts"]
    # The rest of the keys are for platform rules
    platform_rules = {k.lower(): v for k, v in toml_config.items() if k not in top_level_keys}

    config = Config(**toml_config["app"], **toml_config["tts"], platform_rules=platform_rules)
    return config
