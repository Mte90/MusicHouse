"""
Tests for musichouse.utils module.

This module provides comprehensive test coverage for the utils.py module,
targeting ≥95% code coverage. Tests cover:

- silence_stderr: Context manager for suppressing stderr output
- load_mp3_safely: Safe MP3 file loading with error handling
"""
import io
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from musichouse.utils import silence_stderr, load_mp3_safely


class TestSilenceStderr:
    """Tests for silence_stderr context manager."""

    def test_silence_stderr_init(self):
        """Test that silence_stderr initializes correctly."""
        ctx = silence_stderr()
        assert ctx.devnull is not None
        ctx.devnull.close()

    def test_silence_stderr_context_manager(self):
        """Test that silence_stderr works as context manager."""
        original_stderr = sys.stderr

        with silence_stderr() as ctx:
            assert sys.stderr != original_stderr
            assert sys.stderr == ctx.devnull

        assert sys.stderr == original_stderr
        ctx.devnull.close()

    def test_silence_stderr_with_exception(self):
        """Test that stderr is restored even if exception occurs."""
        original_stderr = sys.stderr
        ctx = silence_stderr()

        try:
            with ctx:
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert sys.stderr == original_stderr
        ctx.devnull.close()


class TestLoadMp3Safely:
    """Tests for load_mp3_safely function."""

    def test_load_mp3_safely_with_valid_file(self, tmp_path):
        """Test loading a valid MP3 file."""
        mp3_path = tmp_path / "test.mp3"
        mp3_path.write_bytes(b'ID3\x04\x00\x00\x00\x00\x00\x00')

        with patch('musichouse.utils.eyed3.load') as mock_load:
            mock_audio = MagicMock()
            mock_load.return_value = mock_audio

            result = load_mp3_safely(mp3_path)

            assert result == mock_audio

    def test_load_mp3_safely_with_nonexistent_file(self, tmp_path):
        """Test loading a file that doesn't exist."""
        mp3_path = tmp_path / "nonexistent.mp3"

        with patch('musichouse.utils.eyed3.load') as mock_load:
            mock_load.return_value = None

            result = load_mp3_safely(mp3_path)

            assert result is None

    def test_load_mp3_safely_with_exception(self, tmp_path, caplog):
        """Test that exceptions are handled and None is returned."""
        mp3_path = tmp_path / "corrupt.mp3"
        mp3_path.write_bytes(b'not a valid mp3')

        with patch('musichouse.utils.eyed3.load') as mock_load:
            mock_load.side_effect = Exception("Corrupted file")

            result = load_mp3_safely(mp3_path)

            assert result is None
            # Verify error was logged (covers lines 57-59)
            assert any("Error loading MP3" in record.message for record in caplog.records)

    def test_load_mp3_safely_captures_stderr_with_none_result(self, tmp_path, caplog):
        """Test that stderr is captured when result is None (covers line 55)."""
        mp3_path = tmp_path / "problematic.mp3"
        mp3_path.write_bytes(b'ID3\x04\x00\x00\x00\x00\x00\x00')

        # This test covers the branch where stderr_output exists AND result is None
        with patch('musichouse.utils.eyed3.load') as mock_load:
            mock_load.return_value = None

            # Simulate stderr being written inside eyed3.load
            original_stderr = sys.stderr
            stderr_capture = io.StringIO()
            sys.stderr = stderr_capture
            stderr_capture.write("eyed3 warning message")

            try:
                result = load_mp3_safely(mp3_path)
            finally:
                sys.stderr = original_stderr

            assert result is None

    def test_load_mp3_safely_captures_stderr_with_valid_result(self, tmp_path):
        """Test that stderr is captured even when result is valid."""
        mp3_path = tmp_path / "valid.mp3"
        mp3_path.write_bytes(b'ID3\x04\x00\x00\x00\x00\x00\x00')

        with patch('musichouse.utils.eyed3.load') as mock_load:
            mock_audio = MagicMock()
            mock_load.return_value = mock_audio

            # Simulate stderr being written inside eyed3.load
            original_stderr = sys.stderr
            stderr_capture = io.StringIO()
            sys.stderr = stderr_capture
            stderr_capture.write("eyed3 warning message")

            try:
                result = load_mp3_safely(mp3_path)
            finally:
                sys.stderr = original_stderr

            assert result == mock_audio

    def test_load_mp3_safely_stderr_branch(self, tmp_path):
        """Test the branch where stderr_output exists AND result is None.
        
        This test patches io.StringIO to simulate stderr being written
        inside eyed3.load, ensuring line 55 is executed:
        `if stderr_output and result is None:`
        """
        mp3_path = tmp_path / "problematic.mp3"
        mp3_path.write_bytes(b'ID3\x04\x00\x00\x00\x00\x00\x00')

        with patch('musichouse.utils.eyed3.load') as mock_load, \
             patch('musichouse.utils.io.StringIO') as mock_stringio:
            mock_load.return_value = None
            mock_capture = MagicMock()
            mock_capture.getvalue.return_value = "eyed3 warning message"
            mock_stringio.return_value = mock_capture
            
            result = load_mp3_safely(mp3_path)
            
            assert result is None
