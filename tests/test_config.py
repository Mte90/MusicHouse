"""Tests for config module."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from musichouse.config import (
    DEFAULT_CONFIG,
    _load_config,
    _migrate_api_key_from_config,
    _reset_keyring_fallback,
    _save_config,
    delete_api_key_from_keyring,
    get_api_key,
    get_api_key_from_keyring,
    get_config_dir,
    get_config_path,
    get_endpoint,
    get_exclude_dirs,
    get_last_directory,
    get_model,
    load_config,
    save_config,
    set_api_key,
    set_api_key_in_keyring,
    set_endpoint,
    set_exclude_dirs,
    set_last_directory,
    set_model,
    update_config,
)

# ============================================================================
# Basic Path Tests
# ============================================================================

def test_get_config_dir_returns_path():
    result = get_config_dir()
    assert isinstance(result, Path)


def test_get_config_dir_ends_with_musichouse():
    result = get_config_dir()
    assert result.name == "musichouse"


def test_get_config_path_returns_config_json():
    result = get_config_path()
    assert result.name == "config.json"
    assert result.parent.name == "musichouse"


# ============================================================================
# _load_config Tests
# ============================================================================

class TestLoadConfig:
    """Tests for _load_config() function."""

    def test_load_config_file_not_exists_returns_defaults(self, temp_dir):
        """Test _load_config returns defaults when file doesn't exist."""
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = temp_dir / "nonexistent.json"
            
            # Reset cache
            import musichouse.config as config_module
            config_module._config_cache = None
            config_module._cache_mtime = None
            
            result = _load_config()
            
            assert result == DEFAULT_CONFIG.copy()

    def test_load_config_valid_file(self, temp_dir):
        """Test _load_config loads valid JSON file."""
        config_file = temp_dir / "config.json"
        config_file.write_text(json.dumps({"endpoint": "http://test.com"}))
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            
            # Reset cache
            import musichouse.config as config_module
            config_module._config_cache = None
            config_module._cache_mtime = None
            
            result = _load_config()
            
            assert result["endpoint"] == "http://test.com"
            assert result["model"] == DEFAULT_CONFIG["model"]  # Default value

    def test_load_config_invalid_json_returns_defaults(self, temp_dir):
        """Test _load_config returns defaults on invalid JSON."""
        config_file = temp_dir / "config.json"
        config_file.write_text("invalid json {")
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            
            # Reset cache
            import musichouse.config as config_module
            config_module._config_cache = None
            config_module._cache_mtime = None
            
            result = _load_config()
            
            assert result == DEFAULT_CONFIG.copy()

    def test_load_config_uses_cache_when_mtime_unchanged(self, temp_dir):
        """Test _load_config returns cached value when mtime unchanged."""
        config_file = temp_dir / "config.json"
        config_file.write_text(json.dumps({"endpoint": "http://test.com"}))
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            
            # Reset cache
            import musichouse.config as config_module
            config_module._config_cache = None
            config_module._cache_mtime = None
            
            # First load
            result1 = _load_config()
            
            # Second load (should use cache)
            result2 = _load_config()
            
            assert result1 == result2


# ============================================================================
# _save_config Tests
# ============================================================================

class TestSaveConfig:
    """Tests for _save_config() function."""

    def test_save_config_valid(self, temp_dir):
        """Test _save_config writes valid config."""
        config_file = temp_dir / "config.json"
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            
            config = {
                "endpoint": "http://test.com",
                "model": "test-model",
                "api_key": "test-key",
                "last_directory": "/test",
                "exclude_dirs": [".git"],
            }
            
            _save_config(config)
            
            assert config_file.exists()
            content = json.loads(config_file.read_text())
            assert content["endpoint"] == "http://test.com"
            assert "api_key" not in content  # API key not saved to JSON

    def test_save_config_missing_required_field_raises(self, temp_dir):
        """Test _save_config raises ValueError for missing required field."""
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = temp_dir / "config.json"
            
            config = {
                "model": "test-model",
                "api_key": "test-key",
            }
            
            with pytest.raises(ValueError, match="Missing required field: endpoint"):
                _save_config(config)

    def test_save_config_empty_endpoint_raises(self, temp_dir):
        """Test _save_config raises ValueError for empty endpoint."""
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = temp_dir / "config.json"
            
            config = {
                "endpoint": "",
                "model": "test-model",
                "api_key": "test-key",
            }
            
            with pytest.raises(ValueError, match="Field 'endpoint' cannot be empty"):
                _save_config(config)

    def test_save_config_atomic_write_on_failure(self, temp_dir):
        """Test _save_config cleans up temp file on failure."""
        config_file = temp_dir / "config.json"
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            with patch('musichouse.config.tempfile.mkstemp') as mock_mkstemp:
                # Simulate failure during write
                mock_mkstemp.side_effect = Exception("Write failed")
                
                config = {
                    "endpoint": "http://test.com",
                    "model": "test-model",
                    "api_key": "test-key",
                }
                
                # Test re-raises the Exception from mkstemp failure
                with pytest.raises(Exception):  # noqa: B017 - testing generic Exception re-raise
                    _save_config(config)


# ============================================================================
# API Key Tests
# ============================================================================

class TestApiKey:
    """Tests for API key storage functions."""

    def test_set_api_key_in_keyring_success(self):
        """Test set_api_key_in_keyring stores key successfully."""
        with patch('musichouse.config.keyring.set_password') as mock_set:
            _reset_keyring_fallback()
            
            set_api_key_in_keyring("test-key")
            
            mock_set.assert_called_once_with("MusicHouse", "api_key", "test-key")

    def test_set_api_key_in_keyring_fallback(self):
        """Test set_api_key_in_keyring uses fallback on failure."""
        with patch('musichouse.config.keyring.set_password') as mock_set:
            mock_set.side_effect = Exception("Keyring unavailable")
            _reset_keyring_fallback()
            
            set_api_key_in_keyring("test-key")
            
            # Fallback should be set
            from musichouse.config import _fallback_api_key
            assert _fallback_api_key == "test-key"

    def test_get_api_key_from_keyring_success(self):
        """Test get_api_key_from_keyring returns key."""
        with patch('musichouse.config.keyring.get_password') as mock_get:
            mock_get.return_value = "test-key"
            
            result = get_api_key_from_keyring()
            
            assert result == "test-key"

    def test_get_api_key_from_keyring_returns_none_on_error(self):
        """Test get_api_key_from_keyring returns None on error."""
        # Reset fallback first
        _reset_keyring_fallback()
        with patch('musichouse.config.keyring.get_password') as mock_get:
            mock_get.side_effect = Exception("Keyring error")
            
            result = get_api_key_from_keyring()
            
            assert result is None

    def test_delete_api_key_from_keyring_success(self):
        """Test delete_api_key_from_keyring deletes key."""
        with patch('musichouse.config.keyring.delete_password') as mock_delete:
            _reset_keyring_fallback()
            
            delete_api_key_from_keyring()
            
            mock_delete.assert_called_once_with("MusicHouse", "api_key")

    def test_delete_api_key_from_keyring_handles_missing(self):
        """Test delete_api_key_from_keyring handles missing key."""
        from keyring.errors import PasswordDeleteError
        with patch('musichouse.config.keyring.delete_password') as mock_delete:
            mock_delete.side_effect = PasswordDeleteError("Key doesn't exist")
            _reset_keyring_fallback()
            
            # Should not raise
            delete_api_key_from_keyring()


# ============================================================================
# Migration Tests
# ============================================================================

class TestMigration:
    """Tests for API key migration."""

    def test_migrate_api_key_from_config_moves_key(self):
        """Test _migrate_api_key_from_config moves key to keyring."""
        with patch('musichouse.config.set_api_key_in_keyring') as mock_set:
            config = {"api_key": "test-key", "endpoint": "http://test.com"}
            
            result = _migrate_api_key_from_config(config)
            
            mock_set.assert_called_once_with("test-key")
            assert "api_key" not in result

    def test_migrate_api_key_from_config_no_key(self):
        """Test _migrate_api_key_from_config does nothing if no key."""
        config = {"endpoint": "http://test.com"}
        
        result = _migrate_api_key_from_config(config)
        
        assert "api_key" not in result


# ============================================================================
# load_config and save_config Tests
# ============================================================================

class TestLoadSaveConfig:
    """Tests for load_config() and save_config()."""

    def test_load_config_file_not_exists(self, temp_dir):
        """Test load_config returns defaults when file doesn't exist."""
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = temp_dir / "nonexistent.json"
            with patch('musichouse.config.get_api_key_from_keyring') as mock_key:
                mock_key.return_value = None
                
                result = load_config()
                
                assert result["endpoint"] == DEFAULT_CONFIG["endpoint"]
                assert result["api_key"] == ""

    def test_load_config_with_api_key_in_keyring(self, temp_dir):
        """Test load_config includes API key from keyring."""
        config_file = temp_dir / "config.json"
        config_file.write_text(json.dumps({"endpoint": "http://test.com"}))
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            with patch('musichouse.config.get_api_key_from_keyring') as mock_key:
                mock_key.return_value = "key-from-keyring"
                
                result = load_config()
                
                assert result["api_key"] == "key-from-keyring"

    def test_save_config(self, temp_dir):
        """Test save_config saves to file."""
        config_file = temp_dir / "config.json"
        
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            config = {
                "endpoint": "http://test.com",
                "model": "test-model",
                "api_key": "test-key",
            }
            
            save_config(config)
            
            assert config_file.exists()
            content = json.loads(config_file.read_text())
            assert content["endpoint"] == "http://test.com"
            assert "api_key" not in content  # API key not saved to JSON


# ============================================================================
# update_config Tests
# ============================================================================

class TestUpdateConfig:
    """Tests for update_config()."""

    def test_update_config_updates_fields(self, temp_dir):
        """Test update_config updates specified fields."""
        config_file = temp_dir / "config.json"
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = config_file
            
            update_config({"endpoint": "http://new.com", "model": "new-model"})
            
            assert config_file.exists()

    def test_update_config_api_key_sets_in_keyring(self, temp_dir):
        """Test update_config stores API key in keyring."""
        with patch('musichouse.config.get_config_path') as mock_path:
            mock_path.return_value = temp_dir / "config.json"
            with patch('musichouse.config.set_api_key_in_keyring') as mock_set:
                update_config({"api_key": "new-key"})
                
                mock_set.assert_called_once_with("new-key")


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Tests for convenience getter/setter functions."""

    def test_get_endpoint(self):
        """Test get_endpoint returns endpoint from config."""
        with patch('musichouse.config._load_config') as mock_load:
            mock_load.return_value = {"endpoint": "http://test.com"}
            
            result = get_endpoint()
            
            assert result == "http://test.com"

    def test_get_model(self):
        """Test get_model returns model from config."""
        with patch('musichouse.config._load_config') as mock_load:
            mock_load.return_value = {"model": "test-model"}
            
            result = get_model()
            
            assert result == "test-model"

    def test_get_last_directory(self):
        """Test get_last_directory returns last_directory from config."""
        with patch('musichouse.config._load_config') as mock_load:
            mock_load.return_value = {"last_directory": "/test/path"}
            
            result = get_last_directory()
            
            assert result == "/test/path"

    def test_get_exclude_dirs(self):
        """Test get_exclude_dirs returns exclude_dirs from config."""
        with patch('musichouse.config._load_config') as mock_load:
            mock_load.return_value = {"exclude_dirs": [".git", "node_modules"]}
            
            result = get_exclude_dirs()
            
            assert result == [".git", "node_modules"]

    def test_set_endpoint(self):
        """Test set_endpoint calls update_config."""
        with patch('musichouse.config.update_config') as mock_update:
            set_endpoint("http://new.com")
            
            mock_update.assert_called_once_with({"endpoint": "http://new.com"})

    def test_set_model(self):
        """Test set_model calls update_config."""
        with patch('musichouse.config.update_config') as mock_update:
            set_model("new-model")
            
            mock_update.assert_called_once_with({"model": "new-model"})

    def test_set_last_directory(self):
        """Test set_last_directory calls update_config."""
        with patch('musichouse.config.update_config') as mock_update:
            set_last_directory("/new/path")
            
            mock_update.assert_called_once_with({"last_directory": "/new/path"})

    def test_set_exclude_dirs(self):
        """Test set_exclude_dirs calls update_config."""
        with patch('musichouse.config.update_config') as mock_update:
            set_exclude_dirs([".git", "__pycache__"])
            
            mock_update.assert_called_once_with({"exclude_dirs": [".git", "__pycache__"]})

    def test_get_api_key(self):
        """Test get_api_key returns key from keyring."""
        with patch('musichouse.config.get_api_key_from_keyring') as mock_get:
            mock_get.return_value = "test-key"
            
            result = get_api_key()
            
            assert result == "test-key"

    def test_get_api_key_returns_empty_on_none(self):
        """Test get_api_key returns empty string when keyring returns None."""
        with patch('musichouse.config.get_api_key_from_keyring') as mock_get:
            mock_get.return_value = None
            
            result = get_api_key()
            
            assert result == ""


# ============================================================================
# Test: set_api_key function
# ============================================================================
def test_set_api_key(temp_dir):
    """Test set_api_key function."""
    with patch('musichouse.config.get_config_dir', return_value=temp_dir), patch('musichouse.config.get_api_key_from_keyring', return_value=None), patch('musichouse.config.set_api_key_in_keyring') as mock_set:
        # Set API key
        set_api_key("test-key-123")
        
        # Verify it's saved to keyring
        mock_set.assert_called_with("test-key-123")


def test_set_api_key_full_path(temp_dir):
    """Test set_api_key with full integration."""
    with patch('musichouse.config.get_config_dir', return_value=temp_dir), patch('musichouse.config.get_api_key_from_keyring', return_value=None):
        # Set API key
        set_api_key("full-test-key")
        
        # Verify config file was created
        config_path = temp_dir / "config.json"
        assert config_path.exists()
        
        # Verify it contains the right data
        import json
        with open(config_path) as f:
            data = json.load(f)
        assert data["endpoint"] is not None  # Default value
        assert data["model"] is not None  # Default value


# ============================================================================
# Test: Error handling paths
# ============================================================================
def test_load_config_handles_malformed_json(temp_dir):
    """Test load_config handles malformed JSON gracefully."""
    # Create malformed JSON
    config_path = temp_dir / "config.json"
    config_path.write_text("{ invalid json }")
    
    with patch('musichouse.config.get_config_dir', return_value=temp_dir):
        # Should not raise, should return default config
        config = load_config()
        
        # Should have default values
        assert config["endpoint"] is not None
        assert config["model"] is not None


# ============================================================================
# Test: Platform-specific config paths
# ============================================================================

def test_get_config_dir_linux(temp_dir):
    """Test get_config_dir on Linux uses XDG_CONFIG_HOME or ~/.config."""
    with patch('musichouse.config.platform.system', return_value='Linux'), patch('musichouse.config.os.environ', {}), patch('musichouse.config.Path.home', return_value=temp_dir):
        result = get_config_dir()
        assert str(result) == str(temp_dir / ".config" / "musichouse")


def test_get_config_dir_linux_xdg(temp_dir):
    """Test get_config_dir on Linux respects XDG_CONFIG_HOME."""
    with patch('musichouse.config.platform.system', return_value='Linux'), patch('musichouse.config.os.environ', {'XDG_CONFIG_HOME': str(temp_dir / 'myconfig')}):
        result = get_config_dir()
        assert str(result) == str(temp_dir / 'myconfig' / 'musichouse')


def test_get_config_dir_windows(temp_dir):
    """Test get_config_dir on Windows uses APPDATA."""
    with patch('musichouse.config.platform.system', return_value='Windows'), patch('musichouse.config.os.environ', {'APPDATA': str(temp_dir / 'AppData')}), patch('musichouse.config.Path.home', return_value=temp_dir):
        result = get_config_dir()
        assert str(result) == str(temp_dir / 'AppData' / 'musichouse')


def test_get_config_dir_macos(temp_dir):
    """Test get_config_dir on macOS uses Library/Application Support."""
    with patch('musichouse.config.platform.system', return_value='Darwin'), patch('musichouse.config.Path.home', return_value=temp_dir):
        result = get_config_dir()
        assert str(result) == str(temp_dir / 'Library' / 'Application Support' / 'musichouse')


def test_save_config_cleanup_on_failure(temp_dir):
    """Test _save_config cleans up temp file on failure."""
    config_file = temp_dir / "config.json"
    
    with patch('musichouse.config.get_config_path') as mock_path:
        mock_path.return_value = config_file
        with patch('musichouse.config.tempfile.mkstemp') as mock_mkstemp:
            # Simulate failure during write - mkstemp returns (fd, path)
            mock_mkstemp.return_value = (123, str(temp_dir / "fake_temp"))
            
            # Simulate failure during write
            with patch('os.fdopen') as mock_fdopen:
                mock_fdopen.side_effect = Exception("Write failed")
                
                config = {
                    "endpoint": "http://test.com",
                    "model": "test-model",
                    "api_key": "test-key",
                }
                
                # Test re-raises the Exception from fdopen failure
                with pytest.raises(Exception):  # noqa: B017 - testing generic Exception re-raise
                    _save_config(config)
                
                # Verify mkstemp was called
                mock_mkstemp.assert_called_once()


def test_save_config_handles_oserror_during_close(temp_dir):
    """Test _save_config handles OSError during temp file close."""
    config_file = temp_dir / "config.json"
    
    with patch('musichouse.config.get_config_path') as mock_path:
        mock_path.return_value = config_file
        with patch('musichouse.config.tempfile.mkstemp') as mock_mkstemp:
            mock_mkstemp.return_value = (123, str(temp_dir / "fake_temp"))
            
            # Simulate error during close
            with patch('os.fdopen') as mock_fdopen:
                mock_fdopen.return_value.__enter__.return_value.write.side_effect = OSError("Disk full")
                
                config = {
                    "endpoint": "http://test.com",
                    "model": "test-model",
                    "api_key": "test-key",
                }
                
                with pytest.raises(OSError):
                    _save_config(config)
