# Opens and reads the configuration file, returning a dictionary with the settings.
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    """Load project settings from a YAML file."""
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("The configuration must contain a YAML mapping.")

    return config