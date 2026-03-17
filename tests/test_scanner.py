"""Unit tests for MP3Scanner class."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from musichouse.scanner import MP3Scanner


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def scanner(temp_dir):
    """Create MP3Scanner instance with temporary directory."""
    return MP3Scanner(temp_dir)


# ============================================================================
# Test: Scan directory with valid MP3 files
# ============================================================================
def test_scan_directory_with_mp3_files(mock_mp3_files, scanner):
    """Test scanning a directory with valid MP3 files."""
    # Act
    results = scanner.scan()
    
    # Assert
    assert len(results) == len(mock_mp3_files)
    assert len(results) == 6  # 3 artists × 2 tracks each
    for result in results:
        assert result.suffix.lower() == ".mp3"
        assert result.exists()


def test_scan_returns_copy_of_results(scanner, mock_mp3_files):
    """Test that scan returns a copy, not the internal list."""
    results = scanner.scan()
    
    # Modify returned list
    results.clear()
    
    # Internal list should be unchanged
    assert len(scanner.get_results()) == len(mock_mp3_files)


def test_scan_multiple_times(scanner, mock_mp3_files):
    """Test that scanning multiple times resets results."""
    # First scan
    results1 = scanner.scan()
    assert len(results1) == 6
    
    # Add more files
    (scanner.base_path / "new_artist").mkdir()
    new_file = scanner.base_path / "new_artist" / "new_track.mp3"
    new_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Second scan
    results2 = scanner.scan()
    assert len(results2) == 7  # 6 original + 1 new


# ============================================================================
# Test: Empty directory
# ============================================================================
def test_scan_empty_directory(scanner):
    """Test scanning an empty directory."""
    # Act
    results = scanner.scan()
    
    # Assert
    assert len(results) == 0
    assert scanner.get_file_count() == 0


def test_scan_directory_with_no_mp3_files(temp_dir):
    """Test scanning a directory with no MP3 files."""
    # Create non-MP3 files
    (temp_dir / "file1.txt").write_text("content")
    (temp_dir / "file2.wav").write_bytes(b"fake wav data")
    
    scanner = MP3Scanner(temp_dir)
    results = scanner.scan()
    
    assert len(results) == 0


# ============================================================================
# Test: Progress callback
# ============================================================================
def test_progress_callback_is_called(scanner, mock_mp3_files):
    """Test that progress callback is called for each directory."""
    callback = MagicMock()
    scanner.set_progress_callback(callback)
    
    # Act
    scanner.scan()
    
    # Assert - callback should be called for each directory containing files
    assert callback.called
    # At least called once for the base directory
    assert callback.call_count >= 1


def test_progress_callback_receives_directory_paths(scanner, mock_mp3_files):
    """Test that progress callback receives correct directory paths."""
    callback = MagicMock()
    scanner.set_progress_callback(callback)
    
    # Act
    scanner.scan()
    
    # Assert
    # Check that all calls received string arguments
    for call_args in callback.call_args_list:
        assert isinstance(call_args[0][0], str)


# ============================================================================
# Test: File callback (batch processing)
# ============================================================================
def test_file_callback_is_called_every_batch_size(scanner, mock_mp3_files):
    """Test that file callback is called every batch_size files."""
    callback = MagicMock()
    # Use small batch size for testing
    scanner.set_file_callback(callback, batch_size=2)
    
    # Act
    scanner.scan()
    
    # Assert - should be called at 2, 4, 6 (every 2 files)
    assert callback.called
    # Verify the counts passed to callback
    call_counts = [call[0][0] for call in callback.call_args_list]
    assert 2 in call_counts
    assert 4 in call_counts
    assert 6 in call_counts


def test_file_callback_final_batch(scanner, mock_mp3_files):
    """Test that file callback is called for final incomplete batch."""
    callback = MagicMock()
    # Use batch size that won't divide evenly
    scanner.set_file_callback(callback, batch_size=10)
    
    # Act
    scanner.scan()
    
    # Assert - should be called once for the final batch (6 files)
    assert callback.call_count == 1
    assert callback.call_args[0][0] == 6


def test_file_callback_not_called_without_setup(scanner, mock_mp3_files):
    """Test that file callback is not called if not set."""
    # Don't set file callback
    scanner.scan()
    
    # Should not raise any errors
    assert True


# ============================================================================
# Test: Error handling
# ============================================================================
def test_scan_nonexistent_directory(temp_dir):
    """Test scanning a non-existent directory."""
    non_existent = temp_dir / "does_not_exist"
    scanner = MP3Scanner(non_existent)
    
    # Act
    results = scanner.scan()
    
    # Assert - os.walk returns empty iterator for non-existent dirs
    # No exception is raised, just empty results
    assert len(results) == 0
    assert len(scanner.get_errors()) == 0  # os.walk doesn't raise on non-existent


def test_get_errors_returns_copy(scanner, mock_mp3_files):
    """Test that get_errors returns a copy, not internal list."""
    # Scan first to populate results
    scanner.scan()
    
    # Get errors and verify it's a copy
    errors = scanner.get_errors()
    errors.clear()
    
    # Internal list should be unchanged (still empty since no errors)
    assert len(scanner.get_errors()) == 0


# ============================================================================
# Test: get_results and get_errors
# ============================================================================
def test_get_results(scanner, mock_mp3_files):
    """Test get_results returns correct data."""
    scanner.scan()
    
    results = scanner.get_results()
    assert len(results) == len(mock_mp3_files)
    
    for file_path in results:
        assert isinstance(file_path, Path)
        assert file_path.exists()


def test_get_errors_empty_when_no_errors(scanner, mock_mp3_files):
    """Test get_errors returns empty list when no errors."""
    scanner.scan()
    
    errors = scanner.get_errors()
    assert len(errors) == 0


# ============================================================================
# Test: get_file_count
# ============================================================================
def test_get_file_count(scanner, mock_mp3_files):
    """Test get_file_count returns correct count."""
    scanner.scan()
    
    assert scanner.get_file_count() == len(mock_mp3_files)


def test_get_file_count_zero_for_empty_dir(scanner):
    """Test get_file_count returns 0 for empty directory."""
    scanner.scan()
    
    assert scanner.get_file_count() == 0


# ============================================================================
# Test: Recursive scanning
# ============================================================================
def test_recursive_scanning(temp_dir):
    """Test that scanner recursively scans subdirectories."""
    # Create nested structure
    level1 = temp_dir / "level1"
    level2 = level1 / "level2"
    level3 = level2 / "level3"
    level3.mkdir(parents=True)
    
    # Create MP3 at each level
    (temp_dir / "root.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (level1 / "level1.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (level2 / "level2.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (level3 / "level3.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    scanner = MP3Scanner(temp_dir)
    results = scanner.scan()
    
    assert len(results) == 4
    assert any("root.mp3" in str(r) for r in results)
    assert any("level1.mp3" in str(r) for r in results)
    assert any("level2.mp3" in str(r) for r in results)
    assert any("level3.mp3" in str(r) for r in results)


# ============================================================================
# Test: Case insensitive extension matching
# ============================================================================
def test_case_insensitive_extension(temp_dir):
    """Test that .MP3 and .Mp3 are also recognized."""
    # Create files with different case extensions
    (temp_dir / "file1.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (temp_dir / "file2.MP3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (temp_dir / "file3.Mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (temp_dir / "file4.wav").write_bytes(b"fake wav")
    
    scanner = MP3Scanner(temp_dir)
    results = scanner.scan()
    
    assert len(results) == 3


# ============================================================================
# Test: set_progress_callback and set_file_callback
# ============================================================================
def test_set_progress_callback(scanner):
    """Test setting progress callback."""
    callback = MagicMock()
    scanner.set_progress_callback(callback)
    
    assert scanner._progress_callback == callback


def test_set_file_callback(scanner):
    """Test setting file callback with default batch size."""
    callback = MagicMock()
    scanner.set_file_callback(callback)
    
    assert scanner._file_callback == callback
    assert scanner._file_callback_batch_size == 100


def test_set_file_callback_custom_batch_size(scanner):
    """Test setting file callback with custom batch size."""
    callback = MagicMock()
    scanner.set_file_callback(callback, batch_size=50)
    
    assert scanner._file_callback == callback
    assert scanner._file_callback_batch_size == 50


# ============================================================================
# Test: Stop functionality
# ============================================================================
def test_stop_during_scan(scanner, mock_mp3_files):
    """Test that scan stops when stop() is called."""
    # Set up a callback that will stop the scanner after first file
    def stop_after_first(file_count):
        if file_count >= 1:
            scanner.stop()
    scanner.set_file_callback(stop_after_first)
    
    # Also set progress callback to trigger stop during directory iteration
    def stop_after_first_dir(dir_path):
        if stop_after_first_dir.call_count >= 1:
            scanner.stop()
    stop_after_first_dir.call_count = 0
    scanner.set_progress_callback(stop_after_first_dir)
    
    # Act
    results = scanner.scan()
    
    # Assert - is_stopped() should return True
    assert scanner.is_stopped()


def test_is_stopped_returns_false_when_not_stopped(scanner):
    """Test that is_stopped returns False before stop()."""
    # Assert
    assert not scanner.is_stopped()
    
    # Scan without stopping
    scanner.scan()
    
    # Still not stopped
    assert not scanner.is_stopped()


def test_stop_method_sets_flag(scanner):
    """Test that stop() sets the internal flag."""
    # Act
    scanner.stop()
    
    # Assert
    assert scanner._stop_requested
    assert scanner.is_stopped()


# ============================================================================
# Test: OSError handling
# ============================================================================
@patch('os.walk')
def test_scan_handles_os_error(mock_walk, temp_dir):
    """Test that OSError during scan is caught and logged."""
    # Make os.walk raise OSError
    mock_walk.side_effect = OSError("Permission denied")
    
    scanner = MP3Scanner(temp_dir)
    
    # Act - should not raise
    results = scanner.scan()
    
    # Assert
    assert len(results) == 0
    assert len(scanner.get_errors()) == 1
    error_path, error_msg = scanner.get_errors()[0]
    assert error_path == temp_dir
    assert "Permission denied" in error_msg


def test_stop_before_scan_starts(scanner):
    """Test that scan stops immediately if stop() called before scan."""
    # Stop before scanning
    scanner.stop()
    
    # Act
    results = scanner.scan()
    
    # Assert - should return empty results immediately
    assert len(results) == 0
    assert scanner.is_stopped()


@patch('musichouse.scanner.logger')
def test_stop_during_directory_iteration(mock_logger, temp_dir):
    """Test that stop during directory iteration logs the message."""
    # Create multiple directories
    dir1 = temp_dir / "dir1"
    dir2 = temp_dir / "dir2"
    dir1.mkdir()
    dir2.mkdir()
    
    # Create MP3 files
    (dir1 / "file1.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    (dir2 / "file2.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    scanner = MP3Scanner(temp_dir)
    
    # Stop after first directory
    def stop_after_first_dir(dir_path):
        if stop_after_first_dir.call_count >= 1:
            scanner.stop()
        stop_after_first_dir.call_count += 1
    stop_after_first_dir.call_count = 0
    scanner.set_progress_callback(stop_after_first_dir)
    
    # Act
    results = scanner.scan()
    
    # Assert - should have stopped during iteration
    assert scanner.is_stopped()
    # Verify logger.info was called with stop message
    assert any("Scan stopped by user" in str(call) for call in mock_logger.info.call_args_list)
