import tomllib
from pathlib import Path

from tts.models import AppConfig, TTSConfig

DEFAULT_CONFIG_PATH = Path("default_config.toml")
CONFIG_PATH = Path("config.toml")


def load_app_config() -> AppConfig:
    configs = _load_config_file(DEFAULT_CONFIG_PATH) if not CONFIG_PATH.is_file() else _load_config_file(CONFIG_PATH)
    return configs[0]


def load_tts_config() -> TTSConfig:
    configs = _load_config_file(DEFAULT_CONFIG_PATH) if not CONFIG_PATH.is_file() else _load_config_file(CONFIG_PATH)
    return configs[1]


def _load_config_file(path: Path) -> tuple[AppConfig, TTSConfig]:
    with path.open("rb") as f:
        toml_config = tomllib.load(f)

    top_level_keys = ["app", "tts"]
    # The rest of the keys are for platform rules
    platform_rules = {k.lower(): v for k, v in toml_config.items() if k not in top_level_keys}

    app_config = AppConfig(**toml_config["app"], platform_rules=platform_rules)
    tts_config = TTSConfig(**toml_config["tts"])

    return app_config, tts_config
