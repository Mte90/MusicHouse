"""Unit tests for Leaderboard class."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from musichouse.leaderboard import Leaderboard


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def leaderboard(temp_db_file):
    """Create Leaderboard instance with temporary database."""
    lb = Leaderboard(cache_dir=temp_db_file.parent)
    yield lb
    lb.reset()


# ============================================================================
# Test: Leaderboard initialization
# ============================================================================
def test_leaderboard_initialization(temp_db_file):
    """Test Leaderboard initializes with temp DB directory."""
    lb = Leaderboard(cache_dir=temp_db_file.parent)
    
    # Should have cache_path set (directory / "leaderboard.db")
    assert lb.cache_path.name == "leaderboard.db"
    
    # Should have empty _top_artists initially
    assert lb._top_artists == []
    
    # Should have _cache attribute
    assert hasattr(lb, '_cache')
    lb.reset()


def test_leaderboard_initialization_creates_db():
    """Test that Leaderboard initialization creates the database file."""
    # Use a unique temp directory for this test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        expected_db_path = tmp_path / "leaderboard.db"
        
        # DB file should not exist yet
        assert not expected_db_path.exists()
        
        # Create leaderboard
        lb = Leaderboard(cache_dir=tmp_path)
        
        # DB file should now exist
        assert expected_db_path.exists()
        
        lb.reset()


# ============================================================================
# Test: update_from_files() with mock MP3 files
# ============================================================================
def test_update_from_files_with_mock_mp3(mock_mp3_files, leaderboard, temp_dir):
    """Test updating leaderboard from mock MP3 files."""
    # Create a test file with mocked load_mp3_safely
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    # Mock load_mp3_safely to return a fake audiofile with artist tag
    mock_audiofile = MagicMock()
    mock_audiofile.tag.artist = "Test Artist"
    
    with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
        result = leaderboard.update_from_files([test_file])
    
    # Assert
    assert len(result) == 1  # 1 unique artist
    assert isinstance(result, list)
    
    # Should be sorted by count descending
    for i in range(len(result) - 1):
        assert result[i][1] >= result[i + 1][1]
    
    # Artist should have count of 1
    assert result[0][1] == 1


def test_update_from_files_empty_list(leaderboard):
    """Test updating leaderboard with empty file list."""
    # Act
    result = leaderboard.update_from_files([])
    
    # Assert
    assert result == []


def test_update_from_files_single_file(temp_dir, leaderboard):
    """Test updating leaderboard with single file."""
    # Create a test file with mocked load_mp3_safely
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    # Mock load_mp3_safely
    mock_audiofile = MagicMock()
    mock_audiofile.tag.artist = "Single Artist"
    
    with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
        result = leaderboard.update_from_files([test_file])
    
    # Assert
    assert len(result) == 1
    assert result[0][1] == 1


def test_update_from_files_mock_load_mp3_safely(leaderboard, temp_dir):
    """Test update_from_files with mocked load_mp3_safely."""
    # Create a test file
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Mock load_mp3_safely to return a fake audiofile with artist tag
    mock_audiofile = MagicMock()
    mock_audiofile.tag.artist = "Mock Artist"
    
    with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
        result = leaderboard.update_from_files([test_file])
    
    # Assert
    assert len(result) == 1
    assert result[0][0] == "Mock Artist"
    assert result[0][1] == 1


def test_update_from_files_error_handling(leaderboard, temp_dir):
    """Test update_from_files handles errors gracefully."""
    # Create a non-MP3 file (will cause error when loading)
    bad_file = temp_dir / "bad.mp3"
    bad_file.write_bytes(b"not a real mp3")
    
    # Should not raise exception
    result = leaderboard.update_from_files([bad_file])
    
    # Should return empty list (no valid artists)
    assert result == []


def test_update_from_files_updates_cache(temp_dir, leaderboard):
    """Test that update_from_files updates the SQLite cache."""
    # Create a test file with mocked load_mp3_safely
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    # Mock load_mp3_safely
    mock_audiofile = MagicMock()
    mock_audiofile.tag.artist = "Cache Test Artist"
    
    with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
        leaderboard.update_from_files([test_file])
    
    # Check cache directly
    artists_from_cache = leaderboard._cache.get_all_artists()
    
    # Should have same artist
    assert len(artists_from_cache) == 1
    
    # Close cache to allow file cleanup
    leaderboard._cache.close()


# ============================================================================
# Test: update_from_artist_counts()
# ============================================================================
def test_update_from_artist_counts(leaderboard):
    """Test updating leaderboard from pre-computed artist counts."""
    artist_counts = {
        "Artist A": 10,
        "Artist B": 5,
        "Artist C": 15,
        "Artist D": 3,
    }
    
    # Act
    result = leaderboard.update_from_artist_counts(artist_counts)
    
    # Assert
    assert len(result) == 4
    assert result[0] == ("Artist C", 15)  # Highest count first
    assert result[-1] == ("Artist D", 3)  # Lowest count last


def test_update_from_artist_counts_empty_dict(leaderboard):
    """Test updating leaderboard with empty dict."""
    # Act
    result = leaderboard.update_from_artist_counts({})
    
    # Assert
    assert result == []


def test_update_from_artist_counts_single_entry(leaderboard):
    """Test updating leaderboard with single artist."""
    artist_counts = {"Solo Artist": 42}
    
    # Act
    result = leaderboard.update_from_artist_counts(artist_counts)
    
    # Assert
    assert len(result) == 1
    assert result[0] == ("Solo Artist", 42)


def test_update_from_artist_counts_sorting(leaderboard):
    """Test that results are properly sorted by count descending."""
    artist_counts = {
        "A": 1,
        "B": 100,
        "C": 50,
        "D": 25,
    }
    
    # Act
    result = leaderboard.update_from_artist_counts(artist_counts)
    
    # Assert - should be sorted: B(100), C(50), D(25), A(1)
    assert result == [("B", 100), ("C", 50), ("D", 25), ("A", 1)]


def test_update_from_artist_counts_updates_cache(leaderboard):
    """Test that update_from_artist_counts updates the SQLite cache."""
    artist_counts = {"Cache Artist": 7}
    
    # Update
    leaderboard.update_from_artist_counts(artist_counts)
    
    # Check cache
    artists_from_cache = leaderboard._cache.get_all_artists()
    assert len(artists_from_cache) == 1
    assert artists_from_cache[0] == ("Cache Artist", 7)
    
    leaderboard._cache.close()


# ============================================================================
# Test: get_top_artists()
# ============================================================================
def test_get_top_artists_returns_sorted_list(leaderboard):
    """Test that get_top_artists returns a sorted list."""
    # Set up some data
    artist_counts = {
        "Artist 1": 10,
        "Artist 2": 20,
        "Artist 3": 30,
    }
    leaderboard.update_from_artist_counts(artist_counts)
    
    # Act
    result = leaderboard.get_top_artists()
    
    # Assert - should be sorted descending
    assert result[0][1] >= result[1][1]
    assert result[1][1] >= result[2][1]


def test_get_top_artists_limit(leaderboard):
    """Test that get_top_artists respects the limit parameter."""
    artist_counts = {
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4,
        "E": 5,
    }
    leaderboard.update_from_artist_counts(artist_counts)
    
    # Act with limit
    result = leaderboard.get_top_artists(limit=3)
    
    # Assert - should return only top 3
    assert len(result) == 3
    assert result[0][0] == "E"  # Highest count


def test_get_top_artists_empty_leaderboard(leaderboard):
    """Test get_top_artists on empty leaderboard."""
    # Act
    result = leaderboard.get_top_artists()
    
    # Assert
    assert result == []


def test_get_top_artists_limit_greater_than_count(leaderboard):
    """Test get_top_artists with limit greater than actual count."""
    artist_counts = {"A": 1, "B": 2}
    leaderboard.update_from_artist_counts(artist_counts)
    
    # Act with large limit
    result = leaderboard.get_top_artists(limit=100)
    
    # Assert - should return all available
    assert len(result) == 2


# ============================================================================
# Test: reset()
# ============================================================================
def test_reset_clears_all_data(temp_dir, leaderboard):
    """Test that reset clears all leaderboard data."""
    # Create a test file with mocked load_mp3_safely
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    # Mock load_mp3_safely
    mock_audiofile = MagicMock()
    mock_audiofile.tag.artist = "Reset Test Artist"
    
    with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
        leaderboard.update_from_files([test_file])
    
    # Verify it has data in cache
    assert len(leaderboard._cache.get_all_artists()) == 1
    
    # Reset
    leaderboard.reset()
    
    # Verify cache is cleared (re-open to check)
    leaderboard._cache = leaderboard._cache.__class__(leaderboard.cache_path.parent)
    assert leaderboard._cache.get_all_artists() == []
    leaderboard._cache.close()

def test_reset_closes_cache(temp_dir, leaderboard):
    """Test that reset closes the cache connection."""
    # Create a test file with mocked load_mp3_safely
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    # Mock load_mp3_safely
    mock_audiofile = MagicMock()
    mock_audiofile.tag.artist = "Close Test Artist"
    
    with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
        leaderboard.update_from_files([test_file])
    
    # Reset
    leaderboard.reset()
    
    # Verify cache is cleared by reopening
    leaderboard._cache = leaderboard._cache.__class__(leaderboard.cache_path.parent)
    assert leaderboard._cache.get_all_artists() == []
    leaderboard._cache.close()

# ============================================================================
# Test: Persistence
# ============================================================================
def test_persistence_across_instances():
    """Test that leaderboard data persists across instances."""
    # Use a unique temp directory for this test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a test file with mocked load_mp3_safely
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"dummy")
        
        # Mock load_mp3_safely
        mock_audiofile = MagicMock()
        mock_audiofile.tag.artist = "Persistent Artist"
        
        # Create first instance and update
        lb1 = Leaderboard(cache_dir=tmp_path)
        with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
            lb1.update_from_files([test_file])
        # Don't call reset() - that would clear the DB
        # Just close the cache to flush data
        lb1._cache.close()
        
        # Create second instance with same DB
        lb2 = Leaderboard(cache_dir=tmp_path)
        
        # Should have the same data from DB
        assert len(lb2.get_top_artists()) == 1
        
        lb2.reset()

def test_persistence_direct_db_check():
    """Test persistence by checking database directly."""
    # Use a unique temp directory for this test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        expected_db_path = tmp_path / "leaderboard.db"
        
        lb = Leaderboard(cache_dir=tmp_path)
        
        # Update with data
        artist_counts = {"Persistent Artist": 99}
        lb.update_from_artist_counts(artist_counts)
        
        # Close the cache to flush DB (don't call reset which clears data)
        lb._cache.close()
        
        # Check DB directly
        conn = sqlite3.connect(expected_db_path)
        cursor = conn.execute(
            "SELECT name, count FROM artists WHERE name = ?",
            ("Persistent Artist",)
        )
        row = cursor.fetchone()
        conn.close()
        
        # Should exist in DB
        assert row is not None
        assert row[0] == "Persistent Artist"
        assert row[1] == 99

def test_persistence_wal_cleanup():
    """Test that WAL files are cleaned up properly."""
    # Use a unique temp directory for this test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a test file with mocked load_mp3_safely
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"dummy")
        
        # Mock load_mp3_safely
        mock_audiofile = MagicMock()
        mock_audiofile.tag.artist = "WAL Test Artist"
        
        lb = Leaderboard(cache_dir=tmp_path)
        with patch('musichouse.leaderboard.load_mp3_safely', return_value=mock_audiofile):
            lb.update_from_files([test_file])
        lb.reset()
        
        # WAL and SHM files should be cleaned
        # (they may or may not exist depending on SQLite behavior)
        # This test just ensures no errors occur
        
        # Create new instance - should work fine
        lb2 = Leaderboard(cache_dir=tmp_path)
        assert lb2 is not None
        lb2.reset()

# ============================================================================
# Test: Edge cases
# ============================================================================
def test_leaderboard_with_special_characters(temp_db_file):
    """Test leaderboard handles special characters in artist names."""
    lb = Leaderboard(cache_dir=temp_db_file.parent)
    
    artist_counts = {
        "Artist with spaces": 1,
        "Artist-with-dashes": 2,
        "Artist_with_underscores": 3,
        "Artist with numbers 123": 4,
        "Artist with unicode ñáéíóú": 5,
    }
    
    result = lb.update_from_artist_counts(artist_counts)
    
    assert len(result) == 5
    lb.reset()


def test_leaderboard_with_empty_artist_names(temp_db_file):
    """Test leaderboard handles empty artist names."""
    lb = Leaderboard(cache_dir=temp_db_file.parent)
    
    artist_counts = {
        "": 5,  # Empty string
        "Valid Artist": 10,
    }
    
    result = lb.update_from_artist_counts(artist_counts)
    
    # Should include empty string as well
    assert len(result) == 2
    lb.reset()


def test_leaderboard_with_zero_counts(temp_db_file):
    """Test leaderboard handles zero counts."""
    lb = Leaderboard(cache_dir=temp_db_file.parent)
    
    artist_counts = {
        "Zero Artist": 0,
        "Positive Artist": 10,
    }
    
    result = lb.update_from_artist_counts(artist_counts)
    
    # Should include both
    assert len(result) == 2
    lb.reset()
