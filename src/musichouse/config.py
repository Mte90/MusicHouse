"""Configuration management for MusicHouse."""

import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import keyring
from keyring.errors import PasswordDeleteError

# Keyring configuration
SERVICE_NAME = "MusicHouse"
API_KEY_USERNAME = "api_key"

# Fallback storage for when keyring is unavailable
_fallback_api_key: Optional[str] = None

# Module-level config cache with mtime tracking
_config_cache: Optional[Dict] = None
_cache_mtime: Optional[float] = None

# Default configuration values
DEFAULT_CONFIG = {
    "endpoint": "http://localhost:8080",
    "model": "default",
    "api_key": "",
    "last_directory": "",
    "exclude_dirs": [".git", "node_modules", ".Trash", "__pycache__"],
}


def get_config_dir() -> Path:
    """Get the application configuration directory without PyQt6 dependency.
    
    Returns:
        Path to config directory:
        - Linux: ~/.config/musichouse
        - macOS: ~/Library/Application Support/musichouse
        - Windows: ~/AppData/Roaming/musichouse
    """
    system = platform.system()
    
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    
    config_dir = base / "musichouse"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the full path to config.json."""
    return get_config_dir() / "config.json"


def _load_config() -> Dict:
    """Load config with mtime check.
    
    Returns cached config if file hasn't changed since last load.
    Merges with defaults and adds API key from keyring.
    """
    global _config_cache, _cache_mtime
    
    config_path = get_config_path()
    
    # File doesn't exist - return defaults with API key from keyring
    if not config_path.exists():
        _config_cache = DEFAULT_CONFIG.copy()
        api_key = get_api_key_from_keyring()
        if api_key is not None:
            _config_cache["api_key"] = api_key
        _cache_mtime = None
        return _config_cache
    
    current_mtime = config_path.stat().st_mtime
    
    if _config_cache is None or _cache_mtime != current_mtime:
        # File changed or first load
        try:
            with open(config_path) as f:
                file_config = json.load(f)
            # Merge with defaults
            _config_cache = DEFAULT_CONFIG.copy()
            _config_cache.update(file_config)
            _cache_mtime = current_mtime
        except (json.JSONDecodeError, IOError):
            # Invalid JSON or IO error - return defaults
            _config_cache = DEFAULT_CONFIG.copy()
            _cache_mtime = current_mtime
    
    # Add API key from keyring
    api_key = get_api_key_from_keyring()
    if api_key is not None:
        _config_cache["api_key"] = api_key
    
    return _config_cache


def update_config(partial: Dict) -> None:
    """Update config with multiple fields atomically.
    
    Args:
        partial: Dict of field names to values.
    """
    config = _load_config()
    # Update only the partial fields (don't overwrite api_key from keyring)
    for key, value in partial.items():
        if key != "api_key":
            config[key] = value
        else:
            # For api_key, update both config and keyring
            config[key] = value
    _save_config(config)


def get_api_key_from_keyring() -> Optional[str]:
    """Get API key from OS keyring.
    
    Returns:
        API key string if found, None otherwise.
    """
    # Check fallback first
    if _fallback_api_key is not None:
        return _fallback_api_key
    
    try:
        return keyring.get_password(SERVICE_NAME, API_KEY_USERNAME)
    except Exception:
        # Keyring might not be available (e.g., headless system)
        return None


def set_api_key_in_keyring(key: str) -> None:
    """Store API key in OS keyring.
    
    Args:
        key: API key to store.
    """
    global _fallback_api_key
    try:
        keyring.set_password(SERVICE_NAME, API_KEY_USERNAME, key)
        _fallback_api_key = key
    except Exception as e:
        # Fallback to in-memory storage if keyring is unavailable
        # This happens in headless environments or when keyring is locked
        _fallback_api_key = key


def delete_api_key_from_keyring() -> None:
    """Delete API key from OS keyring."""
    global _fallback_api_key
    try:
        keyring.delete_password(SERVICE_NAME, API_KEY_USERNAME)
    except PasswordDeleteError:
        # Key doesn't exist, which is fine
        pass
    _fallback_api_key = None


def _reset_keyring_fallback() -> None:
    """Reset the keyring fallback (for testing)."""
    global _fallback_api_key
    _fallback_api_key = None


def _migrate_api_key_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate API key from config.json to keyring.
    
    If api_key exists in config and is non-empty, move it to keyring
    and remove it from config dict.
    
    Args:
        config: Configuration dict loaded from JSON.
        
    Returns:
        Config dict with api_key removed (if migrated).
    """
    api_key = config.get("api_key", "")
    if api_key:
        # Store in keyring
        set_api_key_in_keyring(api_key)
        # Remove from config dict
        config = config.copy()
        del config["api_key"]
    return config


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json and keyring.
    
    API key is retrieved from keyring. Other config values come from config.json.
    If API key exists in config.json (migration case), it's moved to keyring.
    
    Returns:
        Config dict with default values for missing keys.
    """
    config_path = get_config_path()

    if not config_path.exists():
        config = DEFAULT_CONFIG.copy()
    else:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Merge with defaults for missing keys
            merged = DEFAULT_CONFIG.copy()
            merged.update(config)
            config = merged

            # Migrate API key from JSON to keyring if present
            config = _migrate_api_key_from_config(config)
        except (json.JSONDecodeError, IOError):
            config = DEFAULT_CONFIG.copy()

    # Get API key from keyring
    api_key = get_api_key_from_keyring()
    if api_key is not None:
        config["api_key"] = api_key
    else:
        config["api_key"] = DEFAULT_CONFIG["api_key"]

    return config


def _save_config(config: Dict) -> None:
    """Internal save function used by update_config."""
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

    # Store API key in keyring
    set_api_key_in_keyring(config["api_key"])

    # Create config dict without api_key for JSON storage
    config_for_json = {
        "endpoint": config["endpoint"],
        "model": config["model"],
        "last_directory": config.get("last_directory", ""),
        "exclude_dirs": config.get("exclude_dirs", [".git", "node_modules", ".Trash", "__pycache__"]),
    }

    # Atomic write: write to temp file, then rename
    config_dir = config_path.parent
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".tmp", prefix="config_", dir=config_dir
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(config_for_json, f, indent=2)
        # Atomic rename on most filesystems
        os.replace(temp_path, config_path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to config.json and keyring.
    
    API key is stored in keyring, not in config.json.
    Other config values (endpoint, model, last_directory) are saved to config.json.
    
    Args:
        config: Configuration dict with endpoint, model, api_key.
        
    Raises:
        ValueError: If required fields are missing.
    """
    _save_config(config)
    """Save configuration to config.json and keyring.
    
    API key is stored in keyring, not in config.json.
    Other config values (endpoint, model, last_directory) are saved to config.json.
    
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

    # Store API key in keyring
    set_api_key_in_keyring(config["api_key"])

    # Create config dict without api_key for JSON storage
    config_for_json = {
        "endpoint": config["endpoint"],
        "model": config["model"],
        "last_directory": config.get("last_directory", ""),
    }

    # Atomic write: write to temp file, then rename
    config_dir = config_path.parent
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".tmp", prefix="config_", dir=config_dir
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(config_for_json, f, indent=2)
        # Atomic rename on most filesystems
        os.replace(temp_path, config_path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


# Convenience functions
def get_endpoint() -> str:
    config = _load_config()
    return config.get("endpoint", DEFAULT_CONFIG["endpoint"])


def get_model() -> str:
    config = _load_config()
    return config.get("model", DEFAULT_CONFIG["model"])


def get_api_key() -> str:
    config = _load_config()
    return config.get("api_key", DEFAULT_CONFIG["api_key"])


def get_last_directory() -> str:
    config = _load_config()
    return config.get("last_directory", "")


def set_endpoint(endpoint: str) -> None:
    update_config({"endpoint": endpoint})


def set_model(model: str) -> None:
    update_config({"model": model})


def set_api_key(api_key: str) -> None:
    update_config({"api_key": api_key})


def set_last_directory(directory: str) -> None:
    update_config({"last_directory": directory})


def get_exclude_dirs() -> list:
    config = _load_config()
    return config.get("exclude_dirs", [".git", "node_modules", ".Trash", "__pycache__"])


def set_exclude_dirs(exclude_dirs: list) -> None:
    update_config({"exclude_dirs": exclude_dirs})
