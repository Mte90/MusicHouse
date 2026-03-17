"""Tests for config module."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from musichouse.config import (
    get_config_dir, get_config_path, load_config, save_config,
    get_endpoint, get_model, get_api_key, get_last_directory,
    set_endpoint, set_model, set_api_key, set_last_directory,
    DEFAULT_CONFIG
)


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_get_config_dir_returns_path(self):
        """Test that get_config_dir returns a Path object."""
        result = get_config_dir()
        assert isinstance(result, Path)

    def test_get_config_dir_ends_with_musichouse(self):
        """Test that config dir ends with 'musichouse'."""
        result = get_config_dir()
        assert result.name == "musichouse"


class TestGetConfigPath:
    """Tests for get_config_path function."""

    def test_get_config_path_returns_config_json(self):
        """Test that get_config_path returns config.json path."""
        result = get_config_path()
        assert result.name == "config.json"
        assert result.parent.name == "musichouse"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_with_nonexistent_file(self, tmp_path):
        """Test loading config when file doesn't exist returns defaults."""
        with patch('musichouse.config.get_config_path', return_value=tmp_path / "nonexistent.json"):
            config = load_config()
            assert config == DEFAULT_CONFIG.copy()

    def test_load_config_with_valid_file(self, tmp_path):
        """Test loading config from valid file."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": "test-key"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch('musichouse.config.get_config_path', return_value=config_file):
            config = load_config()
            assert config["endpoint"] == "http://test.com"
            assert config["model"] == "test-model"
            assert config["api_key"] == "test-key"

    def test_load_config_merges_with_defaults(self, tmp_path):
        """Test that missing keys are filled with defaults."""
        config_data = {"endpoint": "http://test.com"}  # Missing model and api_key
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch('musichouse.config.get_config_path', return_value=config_file):
            config = load_config()
            assert config["endpoint"] == "http://test.com"
            assert config["model"] == DEFAULT_CONFIG["model"]
            assert config["api_key"] == DEFAULT_CONFIG["api_key"]

    def test_load_config_with_invalid_json(self, tmp_path):
        """Test loading config with invalid JSON returns defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text("invalid json content")

        with patch('musichouse.config.get_config_path', return_value=config_file):
            config = load_config()
            assert config == DEFAULT_CONFIG.copy()

    def test_load_config_with_io_error(self, tmp_path):
        """Test loading config with IO error returns defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        # Mock open to raise IOError
        with patch('musichouse.config.get_config_path', return_value=config_file):
            with patch('builtins.open', side_effect=IOError("Test error")):
                config = load_config()
                assert config == DEFAULT_CONFIG.copy()


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config_valid(self, tmp_path):
        """Test saving valid config."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": "test-key"}
        config_file = tmp_path / "config.json"

        with patch('musichouse.config.get_config_path', return_value=config_file):
            with patch('musichouse.config.Path.mkdir'):
                save_config(config_data)

                assert config_file.exists()
                saved = json.loads(config_file.read_text())
                assert saved == config_data

    def test_save_config_creates_parent_directories(self, tmp_path):
        """Test that save_config creates parent directories."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": "test-key"}
        config_file = tmp_path / "subdir" / "config.json"

        with patch('musichouse.config.get_config_path', return_value=config_file):
            save_config(config_data)

            assert config_file.parent.exists()
            assert config_file.exists()

    def test_save_config_missing_required_field(self, tmp_path):
        """Test saving config with missing required field raises ValueError."""
        config_data = {"endpoint": "http://test.com"}  # Missing model and api_key

        with patch('musichouse.config.get_config_path', return_value=tmp_path / "config.json"):
            with pytest.raises(ValueError, match="Missing required field"):
                save_config(config_data)

    def test_save_config_empty_endpoint_raises_error(self, tmp_path):
        """Test saving config with empty endpoint raises ValueError."""
        config_data = {"endpoint": "", "model": "test-model", "api_key": "test-key"}

        with patch('musichouse.config.get_config_path', return_value=tmp_path / "config.json"):
            with pytest.raises(ValueError, match="Field 'endpoint' cannot be empty"):
                save_config(config_data)

    def test_save_config_empty_model_raises_error(self, tmp_path):
        """Test saving config with empty model raises ValueError."""
        config_data = {"endpoint": "http://test.com", "model": "", "api_key": "test-key"}

        with patch('musichouse.config.get_config_path', return_value=tmp_path / "config.json"):
            with pytest.raises(ValueError, match="Field 'model' cannot be empty"):
                save_config(config_data)

    def test_save_config_empty_api_key_allowed(self, tmp_path):
        """Test that empty api_key is allowed."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": ""}

        with patch('musichouse.config.get_config_path', return_value=tmp_path / "config.json"):
            with patch('musichouse.config.Path.mkdir'):
                # Should not raise
                save_config(config_data)
                assert config_data["api_key"] == ""


class TestGetters:
    """Tests for getter functions."""

    def test_get_endpoint(self, tmp_path):
        """Test get_endpoint returns correct value."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": "key"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch('musichouse.config.get_config_path', return_value=config_file):
            assert get_endpoint() == "http://test.com"

    def test_get_model(self, tmp_path):
        """Test get_model returns correct value."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": "key"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch('musichouse.config.get_config_path', return_value=config_file):
            assert get_model() == "test-model"

    def test_get_api_key(self, tmp_path):
        """Test get_api_key returns correct value."""
        config_data = {"endpoint": "http://test.com", "model": "test-model", "api_key": "secret-key"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch('musichouse.config.get_config_path', return_value=config_file):
            assert get_api_key() == "secret-key"

    def test_get_last_directory(self, tmp_path):
        """Test get_last_directory returns correct value."""
        config_data = {
            "endpoint": "http://test.com",
            "model": "test-model",
            "api_key": "key",
            "last_directory": "/path/to/music"
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch('musichouse.config.get_config_path', return_value=config_file):
            assert get_last_directory() == "/path/to/music"

    def test_getters_with_defaults(self, tmp_path):
        """Test getters return defaults when config missing keys."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch('musichouse.config.get_config_path', return_value=config_file):
            assert get_endpoint() == DEFAULT_CONFIG["endpoint"]
            assert get_model() == DEFAULT_CONFIG["model"]
            assert get_api_key() == DEFAULT_CONFIG["api_key"]
            assert get_last_directory() == ""


class TestSetters:
    """Tests for setter functions."""

    def test_set_endpoint(self, tmp_path):
        """Test set_endpoint saves correctly."""
        config_file = tmp_path / "config.json"

        with patch('musichouse.config.get_config_path', return_value=config_file):
            with patch('musichouse.config.Path.mkdir'):
                set_endpoint("http://new-endpoint.com")

                saved = json.loads(config_file.read_text())
                assert saved["endpoint"] == "http://new-endpoint.com"

    def test_set_model(self, tmp_path):
        """Test set_model saves correctly."""
        config_file = tmp_path / "config.json"

        with patch('musichouse.config.get_config_path', return_value=config_file):
            with patch('musichouse.config.Path.mkdir'):
                set_model("new-model")

                saved = json.loads(config_file.read_text())
                assert saved["model"] == "new-model"

    def test_set_api_key(self, tmp_path):
        """Test set_api_key saves correctly."""
        config_file = tmp_path / "config.json"

        with patch('musichouse.config.get_config_path', return_value=config_file):
            with patch('musichouse.config.Path.mkdir'):
                set_api_key("new-secret-key")

                saved = json.loads(config_file.read_text())
                assert saved["api_key"] == "new-secret-key"

    def test_set_last_directory(self, tmp_path):
        """Test set_last_directory saves correctly."""
        config_file = tmp_path / "config.json"

        with patch('musichouse.config.get_config_path', return_value=config_file):
            with patch('musichouse.config.Path.mkdir'):
                set_last_directory("/new/music/path")

                saved = json.loads(config_file.read_text())
                assert saved["last_directory"] == "/new/music/path"
