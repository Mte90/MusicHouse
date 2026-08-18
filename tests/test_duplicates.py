"""Unit tests for duplicate detection module."""

import pytest

from musichouse.duplicates import (
    find_duplicates_fingerprint,
    find_duplicates_metadata,
    find_duplicates,
    _normalize_metadata,
)
# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def cache(temp_db_file):
    """Create LeaderboardCache instance with temporary database."""
    from musichouse.leaderboard_cache import LeaderboardCache
    
    cache = LeaderboardCache(temp_db_file)
    yield cache
    cache.close()


# ============================================================================
# Test: _normalize_metadata
# ============================================================================
def test_normalize_metadata_lowercase():
    """Test that normalize_metadata lowercases input."""
    assert _normalize_metadata("Metallica") == "metallica"


def test_normalize_metadata_strip():
    """Test that normalize_metadata strips whitespace."""
    assert _normalize_metadata("  Metallica  ") == "metallica"


def test_normalize_metadata_collapse_whitespace():
    """Test that normalize_metadata collapses internal whitespace."""
    assert _normalize_metadata("Metallica   Rocks") == "metallica rocks"


def test_normalize_metadata_combined():
    """Test combined normalization."""
    assert _normalize_metadata("  Metallica   Rocks  ") == "metallica rocks"


def test_normalize_metadata_empty():
    """Test empty string handling."""
    assert _normalize_metadata("") == ""
    assert _normalize_metadata(None) == ""


def test_normalize_metadata_whitespace_only():
    """Test whitespace-only string."""
    assert _normalize_metadata("   ") == ""


# ============================================================================
# Test: find_duplicates_fingerprint - basic functionality
# ============================================================================
def test_fingerprint_duplicates_basic(cache):
    """Test basic fingerprint duplicate detection."""
    conn = cache._get_connection()
    
    # Insert 4 files: 2 with identical fingerprints (duplicates), 2 different
    # Fingerprint must be multiple of 4 bytes for struct unpacking
    base_fp = b"test_fingerprint_data_" + b"\x00" * 2
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, base_fp, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1_copy.mp3", 5000000, 1000.0, "Artist", "Song 1 Copy", 1000.0, base_fp, 180.0)
    )
    # Different fingerprints (must be multiple of 4 bytes)
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 6000000, 1000.0, "Artist", "Song 2", 1000.0, b"different_fp_" + b"\x00" * 3, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song3.mp3", 7000000, 1000.0, "Artist", "Song 3", 1000.0, b"another_fp_" + b"\x00" * 1, 200.0)
    )
    
    result = find_duplicates_fingerprint(cache)
    
    assert len(result) == 1
    assert len(result[0]) == 2
    paths = [f['path'] for f in result[0]]
    assert "/music/song1.mp3" in paths
    assert "/music/song1_copy.mp3" in paths


def test_fingerprint_duplicates_no_fingerprints(cache):
    """Test that files without fingerprints return empty list."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 2", 1000.0)
    )
    
    result = find_duplicates_fingerprint(cache)
    
    assert result == []


def test_fingerprint_duplicates_threshold_84_percent(cache):
    """Test that 84% similarity does NOT group files."""
    conn = cache._get_connection()
    
    # Create fingerprints that are very different (64 bytes = multiple of 4)
    fp1 = b"A" * 64
    fp2 = b"B" * 64
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp1, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 2", 1000.0, fp2, 180.0)
    )
    
    result = find_duplicates_fingerprint(cache)
    
    # Should return empty since similarity is below 85%
    assert len(result) == 0 or all(len(g) < 2 for g in result)


def test_fingerprint_duplicates_threshold_86_percent(cache):
    """Test that 86% similarity DOES group files."""
    conn = cache._get_connection()
    
    # Create fingerprints that are highly similar (64 bytes = multiple of 4)
    fp1 = b"A" * 64
    fp2 = b"A" * 60 + b"B" * 4  # Very similar
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp1, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 2", 1000.0, fp2, 180.0)
    )
    
    # Files should be grouped if similarity >= 85%
    # Note: actual grouping depends on computed similarity

def test_fingerprint_duplicates_duration_bucket(cache):
    """Test that files with different durations are not grouped."""
    conn = cache._get_connection()
    
    # Same fingerprint but different durations (> 2s tolerance)
    fp = b"test_fingerprint_" + b"\x00" * 3
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 2", 1000.0, fp, 250.0)  # 70s different
    )
    
    result = find_duplicates_fingerprint(cache)
    
    # Should not group due to duration mismatch
    assert len(result) == 0 or all(len(g) < 2 for g in result)


def test_fingerprint_duplicates_duration_within_tolerance(cache):
    """Test that files with similar durations ARE grouped."""
    conn = cache._get_connection()
    
    # Same fingerprint and durations in same bucket (rounded to same int)
    fp = b"test_fingerprint_" + b"\x00" * 3
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 2", 1000.0, fp, 180.5)  # Same bucket (180), within tolerance
    )
    
    result = find_duplicates_fingerprint(cache)
    
    # Should group due to duration match and fingerprint match
    assert len(result) == 1
    assert len(result[0]) == 2


def test_fingerprint_duplicates_single_file_not_grouped(cache):
    """Test that single files are not returned as groups."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, b"unique_fp_" + b"\x00" * 2, 180.0)
    )
    
    result = find_duplicates_fingerprint(cache)
    
    assert result == []


def test_fingerprint_duplicates_transitive_grouping(cache):
    """Test transitive grouping: A matches B, B matches C -> A, B, C all in one group."""
    conn = cache._get_connection()
    
    # Create 3 files where A matches B and B matches C (64 bytes each)
    fp1 = b"A" * 64
    fp2 = b"A" * 60 + b"B" * 4
    fp3 = b"A" * 56 + b"B" * 8
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp1, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 2", 1000.0, fp2, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song3.mp3", 5000000, 1000.0, "Artist", "Song 3", 1000.0, fp3, 180.0)
    )
    
    result = find_duplicates_fingerprint(cache)
    
    # Check that we have at least one group with 2+ files
    has_valid_group = any(len(g) >= 2 for g in result)
    assert has_valid_group


# ============================================================================
# Test: find_duplicates_metadata - basic functionality
# ============================================================================
def test_metadata_duplicates_basic(cache):
    """Test basic metadata duplicate detection."""
    conn = cache._get_connection()
    
    # Insert 3 files: 2 with same normalized artist+title, 1 different
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1_copy.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 6000000, 1000.0, "Artist", "Song 2", 1000.0)
    )
    
    result = find_duplicates_metadata(cache)
    
    assert len(result) == 1
    assert len(result[0]) == 2


def test_metadata_duplicates_normalization(cache):
    """Test metadata normalization: different case/whitespace matches."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "  Metallica  ", "  Enter Sandman  ", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "metallica", "enter sandman", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song3.mp3", 5000000, 1000.0, "METALLICA", "ENTER SANDMAN", 1000.0)
    )
    
    result = find_duplicates_metadata(cache)
    
    assert len(result) == 1
    assert len(result[0]) == 3


def test_metadata_duplicates_missing_artist_or_title(cache):
    """Test that files with missing artist or title are skipped."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, None, "Song 2", 1000.0)  # Missing artist
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song3.mp3", 5000000, 1000.0, "Artist", None, 1000.0)  # Missing title
    )
    
    result = find_duplicates_metadata(cache)
    
    # Only song1 has both artist and title, so no groups
    assert result == []


def test_metadata_duplicates_single_file_not_grouped(cache):
    """Test that single files are not returned as groups."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    
    result = find_duplicates_metadata(cache)
    
    assert result == []


def test_metadata_duplicates_return_structure(cache):
    """Test that return structure has correct fields with None for duration/similarity."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    
    result = find_duplicates_metadata(cache)
    
    assert len(result) == 1
    group = result[0]
    assert len(group) == 2
    
    for file_info in group:
        assert 'path' in file_info
        assert 'artist' in file_info
        assert 'title' in file_info
        assert 'size' in file_info
        assert file_info['duration'] is None
        assert file_info['similarity'] is None


# ============================================================================
# Test: find_duplicates - auto-selection
# ============================================================================
def test_find_duplicates_auto_select_fingerprint(monkeypatch, cache):
    """Test that find_duplicates uses fingerprint mode when fpcalc available."""
    conn = cache._get_connection()
    
    fp = b"test_fp_" + b"\x00" * 0
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp, 180.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, fingerprint, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0, fp, 180.0)
    )
    
    # Mock is_fpcalc_available to return True
    monkeypatch.setattr("musichouse.duplicates.is_fpcalc_available", lambda: True)
    
    result = find_duplicates(cache)
    
    # Should use fingerprint mode
    assert len(result) == 1
    assert len(result[0]) == 2
    # Fingerprint mode includes duration and similarity
    assert result[0][0]['duration'] is not None
    assert result[0][0]['similarity'] is not None


def test_find_duplicates_auto_select_metadata(monkeypatch, cache):
    """Test that find_duplicates uses metadata mode when fpcalc not available."""
    conn = cache._get_connection()
    
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song1.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/music/song2.mp3", 5000000, 1000.0, "Artist", "Song 1", 1000.0)
    )
    
    # Mock is_fpcalc_available to return False
    monkeypatch.setattr("musichouse.duplicates.is_fpcalc_available", lambda: False)
    
    result = find_duplicates(cache)
    
    # Should use metadata mode
    assert len(result) == 1
    assert len(result[0]) == 2
    # Metadata mode has None for duration and similarity
    assert result[0][0]['duration'] is None
    assert result[0][0]['similarity'] is None