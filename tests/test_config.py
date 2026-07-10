"""Minimal tests for config module."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from musichouse.config import get_config_dir, get_config_path, DEFAULT_CONFIG


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
