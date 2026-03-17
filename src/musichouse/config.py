"""Configuration management for MusicHouse."""

import json
from pathlib import Path
from typing import Any, Dict
from PyQt6.QtCore import QStandardPaths


# Default configuration values
DEFAULT_CONFIG = {
    "endpoint": "http://localhost:8080",
    "model": "default",
    "api_key": "",
    "last_directory": "",
}


def get_config_dir() -> Path:
    """Get the application configuration directory.
    
    Returns ~/.config/musichouse on Linux.
    """
    return Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.ConfigLocation
        )
    ) / "musichouse"


def get_config_path() -> Path:
    """Get the full path to config.json."""
    return get_config_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json.
    
    Returns config dict with default values for missing keys.
    """
    config_path = get_config_path()

    if not config_path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Merge with defaults for missing keys
        merged = DEFAULT_CONFIG.copy()
        merged.update(config)
        return merged
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to config.json.
    
    Args:
        config: Configuration dict with endpoint, model, api_key.
        
    Raises:
        ValueError: If required fields are missing.
    """
    # Validate required fields
    required_fields = ["endpoint", "model", "api_key"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
        if not config[field] and field != "api_key":
            # api_key can be empty, endpoint and model cannot
            raise ValueError(f"Field '{field}' cannot be empty")

    # Ensure config directory exists
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# Convenience functions
def get_endpoint() -> str:
    config = load_config()
    return config.get("endpoint", DEFAULT_CONFIG["endpoint"])


def get_model() -> str:
    config = load_config()
    return config.get("model", DEFAULT_CONFIG["model"])


def get_api_key() -> str:
    config = load_config()
    return config.get("api_key", DEFAULT_CONFIG["api_key"])


def get_last_directory() -> str:
    config = load_config()
    return config.get("last_directory", "")


def set_endpoint(endpoint: str) -> None:
    config = load_config()
    config["endpoint"] = endpoint
    save_config(config)


def set_model(model: str) -> None:
    config = load_config()
    config["model"] = model
    save_config(config)


def set_api_key(api_key: str) -> None:
    config = load_config()
    config["api_key"] = api_key
    save_config(config)


def set_last_directory(directory: str) -> None:
    config = load_config()
    config["last_directory"] = directory
    save_config(config)
