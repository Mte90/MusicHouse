"""Unit tests for LeaderboardCache class."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from musichouse.leaderboard_cache import LeaderboardCache


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def cache(temp_db_file):
    """Create LeaderboardCache instance with temporary database."""
    cache = LeaderboardCache(temp_db_file)
    yield cache
    cache.close()


# ============================================================================
# Test: update_artists() - insert and update
# ============================================================================
def test_update_artists_insert(cache):
    """Test inserting new artists."""
    # Act
    cache.update_artists({"Artist A": 5, "Artist B": 3})
    
    # Assert
    top = cache.get_top_artists()
    assert len(top) == 2
    assert ("Artist A", 5) in top
    assert ("Artist B", 3) in top


def test_update_artists_update(cache):
    """Test updating existing artists (increment count)."""
    # Act - insert first
    cache.update_artists({"Artist A": 5})
    
    # Act - update same artist
    cache.update_artists({"Artist A": 3})
    
    # Assert - count should be incremented (5 + 3 = 8)
    top = cache.get_top_artists()
    assert len(top) == 1
    assert ("Artist A", 8) in top


def test_update_artists_multiple_calls(cache):
    """Test multiple update calls."""
    # Act
    cache.update_artists({"Artist A": 5})
    cache.update_artists({"Artist B": 3})
    cache.update_artists({"Artist A": 2})
    
    # Assert
    top = cache.get_top_artists()
    assert len(top) == 2
    assert ("Artist A", 7) in top  # 5 + 2
    assert ("Artist B", 3) in top


# ============================================================================
# Test: get_top_artists() - sorted by count
# ============================================================================
def test_get_top_artists_sorted(cache):
    """Test that top artists are sorted by count descending."""
    # Act
    cache.update_artists({
        "Artist A": 10,
        "Artist B": 5,
        "Artist C": 15,
        "Artist D": 3
    })
    
    # Act - get top 2
    top = cache.get_top_artists(limit=2)
    
    # Assert
    assert len(top) == 2
    assert top[0] == ("Artist C", 15)
    assert top[1] == ("Artist A", 10)


def test_get_top_artists_default_limit(cache):
    """Test default limit of 10."""
    # Act
    for i in range(15):
        cache.update_artists({f"Artist {i}": i})
    
    # Act - get top with default limit
    top = cache.get_top_artists()
    
    # Assert
    assert len(top) == 10


def test_get_top_artists_empty(cache):
    """Test getting top artists from empty database."""
    # Act
    top = cache.get_top_artists()
    
    # Assert
    assert top == []


# ============================================================================
# Test: get_all_artists() - all artists
# ============================================================================
def test_get_all_artists(cache):
    """Test getting all artists sorted by count."""
    # Act
    cache.update_artists({
        "Artist A": 10,
        "Artist B": 5,
        "Artist C": 15
    })
    
    # Act
    all_artists = cache.get_all_artists()
    
    # Assert
    assert len(all_artists) == 3
    assert all_artists[0] == ("Artist C", 15)
    assert all_artists[1] == ("Artist A", 10)
    assert all_artists[2] == ("Artist B", 5)


def test_get_all_artists_empty(cache):
    """Test getting all artists from empty database."""
    # Act
    all_artists = cache.get_all_artists()
    
    # Assert
    assert all_artists == []


# ============================================================================
# Test: clear() - delete all data
# ============================================================================
def test_clear_artists(cache):
    """Test clearing all artist data."""
    # Act - add data
    cache.update_artists({"Artist A": 10})
    assert len(cache.get_all_artists()) == 1
    
    # Act - clear
    cache.clear()
    
    # Assert
    assert cache.get_all_artists() == []


def test_clear_similar_artists(cache):
    """Test clearing similar artists data."""
    # Act - insert similar artist data directly
    conn = cache._get_connection()
    conn.execute(
        "INSERT INTO similar_artists (artist_name, similar_json, last_updated) VALUES (?, ?, ?)",
        ("Artist A", '["Artist B"]', 123456)
    )
    
    # Act - clear
    cache.clear()
    
    # Assert
    cursor = conn.execute("SELECT * FROM similar_artists")
    assert cursor.fetchall() == []


def test_clear_scan_cache(cache):
    """Test clearing scan cache data."""
    # Act - insert scan cache data directly
    conn = cache._get_connection()
    conn.execute(
        "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time) VALUES (?, ?, ?, ?, ?, ?)",
        ("/path/to/file.mp3", 1234, 123456.0, "Artist", "Title", 123456.0)
    )
    
    # Act - clear
    cache.clear()
    
    # Assert
    cursor = conn.execute("SELECT * FROM scan_cache")
    assert cursor.fetchall() == []


# ============================================================================
# Test: get_cached_info() - retrieve cached info
# ============================================================================
def test_get_cached_info_exists(cache):
    """Test getting cached info for existing file."""
    # Act - insert data
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 1234,
            'mtime': 123456.0,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Act
    info = cache.get_cached_info('/path/to/file.mp3')
    
    # Assert
    assert info is not None
    assert info['path'] == '/path/to/file.mp3'
    assert info['size'] == 1234
    assert info['mtime'] == 123456.0
    assert info['artist'] == 'Artist'
    assert info['title'] == 'Title'
    assert 'scan_time' in info


def test_get_cached_info_not_exists(cache):
    """Test getting cached info for non-existing file."""
    # Act
    info = cache.get_cached_info('/nonexistent/path.mp3')
    
    # Assert
    assert info is None


# ============================================================================
# Test: update_scan_cache() - batch update
# ============================================================================
def test_update_scan_cache(cache):
    """Test updating scan cache with file info."""
    # Act
    cache.update_scan_cache([
        {
            'path': '/path/to/file1.mp3',
            'size': 1234,
            'mtime': 123456.0,
            'artist': 'Artist 1',
            'title': 'Title 1'
        },
        {
            'path': '/path/to/file2.mp3',
            'size': 5678,
            'mtime': 123457.0,
            'artist': 'Artist 2',
            'title': 'Title 2'
        }
    ])
    
    # Assert
    info1 = cache.get_cached_info('/path/to/file1.mp3')
    info2 = cache.get_cached_info('/path/to/file2.mp3')
    
    assert info1 is not None
    assert info1['artist'] == 'Artist 1'
    assert info1['title'] == 'Title 1'
    
    assert info2 is not None
    assert info2['artist'] == 'Artist 2'
    assert info2['title'] == 'Title 2'


def test_update_scan_cache_overwrite(cache):
    """Test that update_scan_cache overwrites existing entries."""
    # Act - insert first
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 1234,
            'mtime': 123456.0,
            'artist': 'Old Artist',
            'title': 'Old Title'
        }
    ])
    
    # Act - update same file
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 5678,
            'mtime': 123457.0,
            'artist': 'New Artist',
            'title': 'New Title'
        }
    ])
    
    # Assert
    info = cache.get_cached_info('/path/to/file.mp3')
    assert info['size'] == 5678
    assert info['mtime'] == 123457.0
    assert info['artist'] == 'New Artist'
    assert info['title'] == 'New Title'


def test_update_scan_cache_optional_fields(cache):
    """Test scan cache with optional artist/title fields."""
    # Act
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 1234,
            'mtime': 123456.0
            # No artist or title
        }
    ])
    
    # Assert
    info = cache.get_cached_info('/path/to/file.mp3')
    assert info is not None
    assert info['artist'] is None
    assert info['title'] is None


# ============================================================================
# Test: get_changed_files() - incremental scan
# ============================================================================
def test_get_changed_files_new_files(cache, temp_dir):
    """Test detecting new files."""
    # Create new MP3 file
    test_file = temp_dir / "new_artist" / "new_track.mp3"
    test_file.parent.mkdir()
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Act
    changed, new_count, modified_count, skipped = cache.get_changed_files(temp_dir)
    
    # Assert
    assert len(changed) == 1
    assert new_count == 1
    assert modified_count == 0
    assert skipped == 0


def test_get_changed_files_modified_files(cache, temp_dir):
    """Test detecting modified files."""
    # Create file
    test_file = temp_dir / "artist" / "track.mp3"
    test_file.parent.mkdir()
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Cache initial state
    stat = test_file.stat()
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Modify file
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 200)
    
    # Act
    changed, new_count, modified_count, skipped = cache.get_changed_files(temp_dir)
    
    # Assert
    assert len(changed) == 1
    assert new_count == 0
    assert modified_count == 1
    assert skipped == 0


def test_get_changed_files_unchanged_files(cache, temp_dir):
    """Test detecting unchanged files."""
    # Create file
    test_file = temp_dir / "artist" / "track.mp3"
    test_file.parent.mkdir()
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Cache initial state
    stat = test_file.stat()
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Act (no modification)
    changed, new_count, modified_count, skipped = cache.get_changed_files(temp_dir)
    
    # Assert
    assert len(changed) == 0
    assert new_count == 0
    assert modified_count == 0
    assert skipped == 1


def test_get_changed_files_mixed(cache, temp_dir):
    """Test detecting mix of new, modified, and unchanged files."""
    # Create new file
    new_file = temp_dir / "new_artist" / "new_track.mp3"
    new_file.parent.mkdir()
    new_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Create and cache modified file
    mod_file = temp_dir / "mod_artist" / "mod_track.mp3"
    mod_file.parent.mkdir()
    mod_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    mod_stat = mod_file.stat()
    cache.update_scan_cache([
        {
            'path': str(mod_file),
            'size': mod_stat.st_size,
            'mtime': mod_stat.st_mtime,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    mod_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 200)
    
    # Create and cache unchanged file
    unch_file = temp_dir / "unch_artist" / "unch_track.mp3"
    unch_file.parent.mkdir()
    unch_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    unch_stat = unch_file.stat()
    cache.update_scan_cache([
        {
            'path': str(unch_file),
            'size': unch_stat.st_size,
            'mtime': unch_stat.st_mtime,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Act
    changed, new_count, modified_count, skipped = cache.get_changed_files(temp_dir)
    
    # Assert
    assert len(changed) == 2
    assert new_count == 1
    assert modified_count == 1
    assert skipped == 1


def test_get_changed_files_non_mp3_ignored(cache, temp_dir):
    """Test that non-MP3 files are ignored."""
    # Create non-MP3 file
    txt_file = temp_dir / "file.txt"
    txt_file.write_text("content")
    
    # Act
    changed, new_count, modified_count, skipped = cache.get_changed_files(temp_dir)
    
    # Assert
    assert len(changed) == 0
    assert new_count == 0
    assert modified_count == 0
    assert skipped == 0


def test_get_changed_files_recursive(cache, temp_dir):
    """Test recursive scanning of subdirectories."""
    # Create nested structure
    level1 = temp_dir / "level1"
    level2 = level1 / "level2"
    level2.mkdir(parents=True)
    
    # Create MP3 at each level
    file1 = temp_dir / "root.mp3"
    file1.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    file2 = level1 / "level1.mp3"
    file2.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    file3 = level2 / "level2.mp3"
    file3.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Act
    changed, new_count, modified_count, skipped = cache.get_changed_files(temp_dir)
    
    # Assert
    assert len(changed) == 3
    assert new_count == 3


# ============================================================================
# Test: close() - cleanup connection
# ============================================================================
def test_close(cache):
    """Test closing database connection."""
    # Act - get connection first
    conn = cache._get_connection()
    assert conn is not None
    
    # Act - close
    cache.close()
    
    # Assert - connection should be None
    assert cache._local.conn is None


def test_close_idempotent(cache):
    """Test that close can be called multiple times."""
    # Act
    cache.close()
    
    # Should not raise
    cache.close()
    
    # Assert
    assert cache._local.conn is None


# ============================================================================
# Test: thread-local connections
# ============================================================================
def test_thread_local_connections(cache):
    """Test that each thread gets its own connection."""
    import threading
    
    connections = []
    
    def get_conn():
        conn = cache._get_connection()
        connections.append(conn)
    
    # Create connections from different threads
    threads = [threading.Thread(target=get_conn) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Assert - all connections should be different
    assert len(connections) == 3
    assert len(set(id(c) for c in connections)) == 3


def test_thread_local_same_connection_in_thread(cache):
    """Test that same thread reuses connection."""
    # Get connection first time
    conn1 = cache._get_connection()
    
    # Get connection second time in same thread
    conn2 = cache._get_connection()
    
    # Assert - should be same connection
    assert conn1 is conn2


# ============================================================================
# Test: WAL mode optimizations
# ============================================================================
def test_wal_mode_enabled(cache):
    """Test that WAL mode is enabled."""
    # Get connection
    conn = cache._get_connection()
    
    # Check journal mode
    cursor = conn.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    
    # Assert
    assert mode == 'wal'


def test_busy_timeout_set(cache):
    """Test that busy timeout is configured."""
    conn = cache._get_connection()
    
    cursor = conn.execute("PRAGMA busy_timeout")
    timeout = cursor.fetchone()[0]
    
    assert timeout == 5000


def test_synchronous_normal(cache):
    """Test that synchronous mode is NORMAL."""
    conn = cache._get_connection()
    
    cursor = conn.execute("PRAGMA synchronous")
    mode = cursor.fetchone()[0]
    
    # NORMAL = 1
    assert mode == 1


# ============================================================================
# Test: Database cleanup after test
# ============================================================================
def test_database_cleanup(temp_db_file):
    """Test that temporary database is cleaned up after test."""
    # Create cache
    cache = LeaderboardCache(temp_db_file)
    cache.update_artists({"Artist A": 10})
    cache.close()
    
    # Assert - database file should exist
    assert temp_db_file.exists()
    
    # Cleanup
    if temp_db_file.exists():
        temp_db_file.unlink()
    for ext in ["-wal", "-shm"]:
        wal_path = temp_db_file.with_suffix(f".db{ext}")
        if wal_path.exists():
            wal_path.unlink()
    
    # Assert - files should be deleted
    assert not temp_db_file.exists()
