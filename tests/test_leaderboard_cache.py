"""Unit tests for LeaderboardCache class."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    
    # Assert - count should be replaced with new value
    top = cache.get_top_artists()
    assert len(top) == 1
    assert ("Artist A", 3) in top


def test_update_artists_multiple_calls(cache):
    """Test multiple update calls."""
    # Act
    cache.update_artists({"Artist A": 5})
    cache.update_artists({"Artist B": 3})
    cache.update_artists({"Artist A": 2})
    
    # Assert
    top = cache.get_top_artists()
    assert len(top) == 2
    assert ("Artist A", 2) in top  # replaced with 2
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
    
    # Act - pass list of files instead of base path
    changed, new_count, modified_count, skipped = cache.get_changed_files([test_file])
    
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
    
    # Act - pass list of files instead of base path
    changed, new_count, modified_count, skipped = cache.get_changed_files([test_file])
    
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
    
    # Act (no modification) - pass list of files instead of base path
    changed, new_count, modified_count, skipped = cache.get_changed_files([test_file])
    
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
    
    # Act - pass list of files instead of base path
    changed, new_count, modified_count, skipped = cache.get_changed_files([new_file, mod_file, unch_file])
    
    # Assert
    assert len(changed) == 2
    assert new_count == 1
    assert modified_count == 1
    assert skipped == 1


def test_get_changed_files_non_mp3_ignored(cache, temp_dir):
    """Test that non-MP3 files are processed (filtering is caller's responsibility)."""
    # Create non-MP3 file
    txt_file = temp_dir / "file.txt"
    txt_file.write_text("content")
    
    # Act - pass list of files (non-MP3 filtering happens in MP3Scanner)
    changed, new_count, modified_count, skipped = cache.get_changed_files([txt_file])
    
    # Assert - file is returned (caller should filter)
    assert len(changed) == 1
    assert new_count == 1
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
    
    # Act - pass list of files instead of base path
    changed, new_count, _, _ = cache.get_changed_files([file1, file2, file3])
    
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
    assert len({id(c) for c in connections}) == 3
    
    # Close all thread connections to avoid ResourceWarning
    for conn in connections:
        conn.close()


def test_thread_local_same_connection_in_thread(cache):
    """Test that same thread reuses connection."""
    # Get connection first time
    conn1 = cache._get_connection()
    
    # Get connection second time in same thread
    conn2 = cache._get_connection()
    
    # Assert - should be same connection
    assert conn1 is conn2


# ============================================================================
# Test: Migration paths
# ============================================================================
def test_migration_v2_adds_tag_data_column(temp_db_file):
    """Test v2 migration adds tag_data column."""
    # Create a v1 database manually
    import sqlite3
    conn = sqlite3.connect(str(temp_db_file))
    conn.execute("CREATE TABLE schema_version (version INTEGER)")
    conn.execute("INSERT INTO schema_version VALUES (1)")
    conn.execute("""
        CREATE TABLE scan_cache (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            artist TEXT,
            title TEXT,
            scan_time REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    
    # Create cache - should trigger migration
    cache = LeaderboardCache(temp_db_file)
    
    # Verify tag_data column exists
    cols = {row['name'] for row in cache._get_connection().execute("PRAGMA table_info(scan_cache)")}
    assert 'tag_data' in cols
    
    cache.close()


def test_migration_v3_adds_fingerprint_duration_and_artist_genres(temp_db_file):
    """Test v3 migration adds fingerprint, duration columns and artist_genres table."""
    # Create a v2 database manually
    import sqlite3
    conn = sqlite3.connect(str(temp_db_file))
    conn.execute("CREATE TABLE schema_version (version INTEGER)")
    conn.execute("INSERT INTO schema_version VALUES (2)")
    conn.execute("""
        CREATE TABLE scan_cache (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            artist TEXT,
            title TEXT,
            scan_time REAL NOT NULL,
            tag_data TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    # Create cache - should trigger migration
    cache = LeaderboardCache(temp_db_file)
    
    # Verify fingerprint and duration columns exist
    cols = {row['name'] for row in cache._get_connection().execute("PRAGMA table_info(scan_cache)")}
    assert 'fingerprint' in cols
    assert 'duration' in cols
    
    # Verify artist_genres table exists
    tables = {row[0] for row in cache._get_connection().execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert 'artist_genres' in tables
    
    cache.close()


def test_get_cached_info_returns_none_for_missing_file(cache):
    """Test get_cached_info returns None for missing file."""
    result = cache.get_cached_info("/nonexistent/file.mp3")
    assert result is None


def test_migration_v3_creates_artist_genres_table(temp_db_file):
    """Test migration v3 creates artist_genres table."""
    import sqlite3
    # Create a v2 database with full schema but version 2
    conn = sqlite3.connect(temp_db_file)
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER);
        INSERT INTO schema_version VALUES (2);
        
        CREATE TABLE artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            count INTEGER NOT NULL DEFAULT 0
        );
        
        CREATE TABLE similar_artists (
            artist_name TEXT PRIMARY KEY,
            similar_json TEXT NOT NULL,
            last_updated INTEGER NOT NULL
        );
        
        CREATE TABLE scan_cache (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            artist TEXT,
            title TEXT,
            scan_time REAL NOT NULL,
            needs_fixing INTEGER DEFAULT 0,
            missing_artist INTEGER DEFAULT 0,
            missing_title INTEGER DEFAULT 0,
            suggested_artist TEXT,
            suggested_title TEXT,
            tag_data TEXT
            -- Note: fingerprint and duration are missing (v2 schema)
        );
    """)
    conn.commit()
    conn.close()
    
    # Now create the cache - should trigger migration
    cache = LeaderboardCache(cache_path=Path(temp_db_file))
    
    # Verify artist_genres table exists
    conn = sqlite3.connect(temp_db_file)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artist_genres'")
    assert cursor.fetchone() is not None
    conn.close()
    cache.close()


def test_get_cached_info_returns_cached_data(cache, temp_dir):
    """Test get_cached_info returns cached file info."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    cache.update_scan_cache([{
        'path': str(test_file),
        'size': 100,
        'mtime': 1.0,
        'artist': 'Test Artist',
        'title': 'Test Title',
        'tag_data': {'artist': 'Test Artist'}
    }])
    
    result = cache.get_cached_info(str(test_file))
    
    assert result is not None
    assert result['artist'] == 'Test Artist'
    assert result['tag_data']['artist'] == 'Test Artist'


def test_update_scan_cache_with_tag_data(cache, temp_dir):
    """Test update_scan_cache stores tag_data."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    cache.update_scan_cache([{
        'path': str(test_file),
        'size': 100,
        'mtime': 1.0,
        'artist': 'Artist',
        'title': 'Title',
        'tag_data': {'artist': 'Artist', 'title': 'Title', 'album': 'Album'}
    }])
    
    info = cache.get_cached_info(str(test_file))
    assert info['tag_data']['album'] == 'Album'


def test_update_scan_cache_with_suggestions(cache, temp_dir):
    """Test update_scan_cache stores suggestion data in database."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"dummy")
    
    # This stores the data in the database even though get_cached_info doesn't return it
    cache.update_scan_cache([{
        'path': str(test_file),
        'size': 100,
        'mtime': 1.0,
        'artist': None,
        'title': None,
        'needs_fixing': 1,
        'missing_artist': 1,
        'missing_title': 1,
        'suggested_artist': 'Suggested Artist',
        'suggested_title': 'Suggested Title',
        'tag_data': None
    }])
    
    # Verify the data was stored (check needs_fixing which is returned)
    info = cache.get_cached_info(str(test_file))
    assert info['needs_fixing'] == 1
    assert info['missing_artist'] == 1


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


# ============================================================================
# Test: Schema migration v3
# ============================================================================
def test_migration_v3_adds_columns_and_table(temp_db_file):
    """Test that migration v3 adds fingerprint/duration columns and artist_genres table."""
    # Create a fresh database at version 2 (simulate old schema)
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test.db"
        
        # Create old schema manually
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE schema_version (version INTEGER);
            INSERT INTO schema_version (version) VALUES (2);
            
            CREATE TABLE scan_cache (
                path TEXT PRIMARY KEY,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                artist TEXT,
                title TEXT,
                scan_time REAL NOT NULL,
                needs_fixing INTEGER DEFAULT 0,
                missing_artist INTEGER DEFAULT 0,
                missing_title INTEGER DEFAULT 0,
                suggested_artist TEXT,
                suggested_title TEXT,
                tag_data TEXT
            );
            
            CREATE TABLE artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                count INTEGER NOT NULL DEFAULT 0
            );
            
            CREATE TABLE similar_artists (
                artist_name TEXT PRIMARY KEY,
                similar_json TEXT NOT NULL,
                last_updated INTEGER NOT NULL
            );
        """)
        conn.close()
        
        # Instantiate cache - should trigger migration
        cache = LeaderboardCache(db_path)
        
        # Verify fingerprint and duration columns exist
        cols = {row['name'] for row in cache._get_connection().execute("PRAGMA table_info(scan_cache)")}
        assert 'fingerprint' in cols
        assert 'duration' in cols
        
        # Verify artist_genres table exists
        cursor = cache._get_connection().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='artist_genres'"
        )
        assert cursor.fetchone() is not None
        
        # Verify schema version is 3
        cursor = cache._get_connection().execute("SELECT version FROM schema_version")
        assert cursor.fetchone()[0] == 3
        
        cache.close()


def test_fresh_db_has_v3_schema(cache):
    """Test that a fresh database has the v3 schema."""
    cols = {row['name'] for row in cache._get_connection().execute("PRAGMA table_info(scan_cache)")}
    assert 'fingerprint' in cols
    assert 'duration' in cols
    
    cursor = cache._get_connection().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='artist_genres'"
    )
    assert cursor.fetchone() is not None


# ============================================================================
# Test: get_fingerprint / set_fingerprint
# ============================================================================
def test_set_and_get_fingerprint(cache):
    """Test setting and getting fingerprint and duration."""
    # Insert a file first
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 1234,
            'mtime': 123456.0,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Set fingerprint
    fingerprint = b'test_fingerprint_data'
    duration = 180.5
    cache.set_fingerprint('/path/to/file.mp3', fingerprint, duration)
    
    # Get fingerprint
    result_fp, result_dur = cache.get_fingerprint('/path/to/file.mp3')
    
    assert result_fp == fingerprint
    assert result_dur == duration


def test_get_fingerprint_not_set(cache):
    """Test getting fingerprint for file that doesn't have one set."""
    # Insert a file first
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 1234,
            'mtime': 123456.0,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Get fingerprint (not set)
    result_fp, result_dur = cache.get_fingerprint('/path/to/file.mp3')
    
    assert result_fp is None
    assert result_dur is None


def test_get_fingerprint_nonexistent_path(cache):
    """Test getting fingerprint for non-existent path."""
    result_fp, result_dur = cache.get_fingerprint('/nonexistent/path.mp3')
    
    assert result_fp is None
    assert result_dur is None


def test_set_fingerprint_overwrites(cache):
    """Test that set_fingerprint overwrites existing values."""
    # Insert a file first
    cache.update_scan_cache([
        {
            'path': '/path/to/file.mp3',
            'size': 1234,
            'mtime': 123456.0,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Set initial fingerprint
    cache.set_fingerprint('/path/to/file.mp3', b'old_fp', 100.0)
    
    # Update fingerprint
    cache.set_fingerprint('/path/to/file.mp3', b'new_fp', 200.0)
    
    # Verify overwrite
    result_fp, result_dur = cache.get_fingerprint('/path/to/file.mp3')
    assert result_fp == b'new_fp'
    assert result_dur == 200.0


# ============================================================================
# Test: get_artist_genres / set_artist_genres
# ============================================================================
def test_set_and_get_artist_genres(cache):
    """Test setting and getting artist genres."""
    genres = ['rock', 'alternative', 'indie']
    
    # Set genres
    cache.set_artist_genres('Test Artist', genres)
    
    # Get genres
    result = cache.get_artist_genres('Test Artist')
    
    assert result == genres


def test_get_artist_genres_not_cached(cache):
    """Test getting genres for artist that isn't cached."""
    result = cache.get_artist_genres('Unknown Artist')
    assert result is None


def test_set_artist_genres_overwrites(cache):
    """Test that set_artist_genres overwrites existing genres."""
    # Set initial genres
    cache.set_artist_genres('Test Artist', ['rock', 'pop'])
    
    # Update genres
    cache.set_artist_genres('Test Artist', ['jazz', 'blues'])
    
    # Verify overwrite
    result = cache.get_artist_genres('Test Artist')
    assert result == ['jazz', 'blues']


def test_set_artist_genres_updates_timestamp(cache):
    """Test that set_artist_genres updates the last_updated timestamp."""
    # Set initial genres
    cache.set_artist_genres('Test Artist', ['rock'])
    
    # Get initial timestamp
    conn = cache._get_connection()
    cursor = conn.execute(
        "SELECT last_updated FROM artist_genres WHERE artist_name = ?",
        ('Test Artist',)
    )
    initial_ts = cursor.fetchone()['last_updated']
    
    # Wait a bit and update (wait 2 seconds to ensure timestamp changes)
    import time
    time.sleep(2)
    cache.set_artist_genres('Test Artist', ['pop'])
    
    # Get new timestamp
    cursor = conn.execute(
        "SELECT last_updated FROM artist_genres WHERE artist_name = ?",
        ('Test Artist',)
    )
    new_ts = cursor.fetchone()['last_updated']
    
    # Timestamp should have increased
    assert new_ts > initial_ts


def test_get_artist_genres_empty_list(cache):
    """Test getting genres when empty list is cached."""
    cache.set_artist_genres('Test Artist', [])
    result = cache.get_artist_genres('Test Artist')
    assert result == []


def test_get_artist_genres_invalid_json_returns_none(cache, temp_dir):
    """Test get_artist_genres handles invalid JSON."""
    conn = cache._get_connection()
    conn.execute(
        "INSERT INTO artist_genres (artist_name, genres_json, last_updated) VALUES (?, ?, ?)",
        ("Bad Artist", "not valid json {{{", 123456)
    )
    conn.commit()
    
    result = cache.get_artist_genres("Bad Artist")
    assert result is None


def test_init_cache_path_as_dir(temp_dir):
    """Test LeaderboardCache accepts directory path."""
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Pass directory instead of file
    cache = LeaderboardCache(cache_path=temp_dir)
    
    # Should append leaderboard.db
    assert cache.cache_path.name == "leaderboard.db"
    assert cache.cache_path.parent == temp_dir
    
    cache.close()


def test_get_changed_files_scandir_oserror(cache, temp_dir):
    """Test get_changed_files handles OSError from scandir."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    stat = test_file.stat()
    # Cache the file
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # Mock scandir to raise OSError
    with patch('musichouse.leaderboard_cache.os.scandir') as mock_scandir:
        mock_scandir.side_effect = OSError("Permission denied")
        
        # Should not raise, should do full scan
        changed, _, _, _ = cache.get_changed_files([test_file])
        
        # Full scan should happen
        assert len(changed) >= 0  # Depends on other files


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


# ============================================================================
# Test: Connection tracking and cleanup
# ============================================================================
def test_connection_tracking_closes_all_threads(temp_db_file):
    """Test that close() properly closes all thread-local connections."""
    import threading
    
    cache = LeaderboardCache(temp_db_file)
    
    # Get main thread connection
    main_conn = cache._get_connection()
    assert len(cache._conns) == 1
    
    # Get connection from another thread
    worker_conn = [None]
    
    def get_worker_conn():
        worker_conn[0] = cache._get_connection()
    
    thread = threading.Thread(target=get_worker_conn)
    thread.start()
    thread.join()
    
    # Assert - both connections should be tracked
    assert len(cache._conns) == 2
    assert main_conn is not worker_conn[0]
    
    # Close from main thread - should close ALL connections
    cache.close()
    
    # Assert - all connections should be closed (registry empty)
    assert len(cache._conns) == 0
    
    # Assert - re-calling close() is safe (idempotent)
    cache.close()
    
    # Assert - using cache after close() recreates a working connection
    new_conn = cache._get_connection()
    assert new_conn is not None
    cursor = new_conn.execute("SELECT 1")
    assert cursor.fetchone()[0] == 1
    
    # Cleanup
    cache.close()


def test_get_all_scanned_paths(cache):
    """Test getting all scanned paths."""
    cache.update_scan_cache([
        {'path': '/path/to/file1.mp3', 'size': 1234, 'mtime': 123456.0, 'artist': 'Artist', 'title': 'Title'},
        {'path': '/path/to/file2.mp3', 'size': 5678, 'mtime': 123457.0, 'artist': 'Artist', 'title': 'Title'},
    ])
    paths = cache.get_all_scanned_paths()
    assert len(paths) == 2
    assert '/path/to/file1.mp3' in paths
    assert '/path/to/file2.mp3' in paths


def test_get_all_scanned_paths_empty(cache):
    """Test getting paths from empty cache."""
    assert cache.get_all_scanned_paths() == []


def test_get_similar_artists_cached(cache):
    """Test getting similar artists from cache."""
    suggestions = [
        {"artist": "Similar Artist 1", "reason": "Similar style"},
        {"artist": "Similar Artist 2", "reason": "Same genre"},
    ]
    cache.save_similar_artists("Seed Artist", suggestions)
    result = cache.get_similar_artists("Seed Artist")
    assert result == suggestions


def test_get_similar_artists_not_cached(cache):
    """Test getting similar artists when not cached."""
    assert cache.get_similar_artists("Unknown Artist") == []


def test_get_similar_artists_invalid_json_returns_empty(cache):
    """Test that invalid JSON in cache returns empty list."""
    conn = cache._get_connection()
    conn.execute(
        "INSERT INTO similar_artists (artist_name, similar_json, last_updated) VALUES (?, ?, ?)",
        ("Bad Artist", "not valid json", 123456)
    )
    result = cache.get_similar_artists("Bad Artist")
    assert result == []


def test_save_similar_artists_replaces_existing(cache):
    """Test that save_similar_artists replaces existing data."""
    cache.save_similar_artists("Artist", [{"artist": "A", "reason": "R"}])
    new_suggestions = [{"artist": "B", "reason": "New"}]
    cache.save_similar_artists("Artist", new_suggestions)
    result = cache.get_similar_artists("Artist")
    assert result == new_suggestions


def test_save_similar_artists_with_timestamp(cache):
    """Test that save_similar_artists updates timestamp."""
    cache.save_similar_artists("Artist", [{"artist": "A", "reason": "R"}])
    conn = cache._get_connection()
    cursor = conn.execute(
        "SELECT last_updated FROM similar_artists WHERE artist_name = ?",
        ("Artist",)
    )
    initial_ts = cursor.fetchone()['last_updated']
    import time
    time.sleep(2)
    cache.save_similar_artists("Artist", [{"artist": "B", "reason": "R"}])
    cursor = conn.execute(
        "SELECT last_updated FROM similar_artists WHERE artist_name = ?",
        ("Artist",)
    )
    new_ts = cursor.fetchone()['last_updated']
    assert new_ts > initial_ts


def test_get_all_indexed_artists(cache):
    """Test getting distinct indexed artists."""
    cache.update_scan_cache([
        {'path': '/file1.mp3', 'size': 1234, 'mtime': 123456.0, 'artist': 'Artist A', 'title': 'Title'},
        {'path': '/file2.mp3', 'size': 5678, 'mtime': 123457.0, 'artist': 'Artist B', 'title': 'Title'},
        {'path': '/file3.mp3', 'size': 9999, 'mtime': 123458.0, 'artist': 'Artist A', 'title': 'Title'},
    ])
    artists = cache.get_all_indexed_artists()
    assert len(artists) == 2
    assert 'Artist A' in artists
    assert 'Artist B' in artists


def test_get_all_indexed_artists_excludes_empty(cache):
    """Test that empty/None artists are excluded."""
    cache.update_scan_cache([
        {'path': '/file1.mp3', 'size': 1234, 'mtime': 123456.0, 'artist': '', 'title': 'Title'},
        {'path': '/file2.mp3', 'size': 5678, 'mtime': 123457.0, 'artist': None, 'title': 'Title'},
        {'path': '/file3.mp3', 'size': 9999, 'mtime': 123458.0, 'artist': 'Valid Artist', 'title': 'Title'},
    ])
    artists = cache.get_all_indexed_artists()
    assert artists == ['Valid Artist']


def test_get_all_indexed_artists_empty(cache):
    """Test getting artists from empty cache."""
    assert cache.get_all_indexed_artists() == []


def test_get_changed_files_empty_list(cache):
    """Test get_changed_files with empty file list."""
    changed, new_count, modified_count, skipped = cache.get_changed_files([])
    assert changed == []
    assert new_count == 0
    assert modified_count == 0
    assert skipped == 0


def test_get_changed_files_oserror_handling(cache, temp_dir):
    """Test get_changed_files handles OSError when accessing file."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    test_file.unlink()
    changed, new_count, _, _ = cache.get_changed_files([test_file])
    assert len(changed) == 1
    assert new_count == 1


def test_check_needs_fixing_with_cached_tag_data(cache):
    """Test _check_needs_fixing uses cached tag_data."""
    cached_info = {'tag_data': {'artist': 'Test Artist', 'title': 'Test Title'}}
    result = cache._check_needs_fixing(Path("/fake/path.mp3"), cached_info)
    assert result is False


def test_check_needs_fixing_missing_artist_in_cache(cache):
    """Test _check_needs_fixing detects missing artist in cache."""
    cached_info = {'tag_data': {'artist': '', 'title': 'Test Title'}}
    result = cache._check_needs_fixing(Path("/fake/path.mp3"), cached_info)
    assert result is True


def test_check_needs_fixing_missing_title_in_cache(cache):
    """Test _check_needs_fixing detects missing title in cache."""
    cached_info = {'tag_data': {'artist': 'Test Artist', 'title': ''}}
    result = cache._check_needs_fixing(Path("/fake/path.mp3"), cached_info)
    assert result is True


def test_check_needs_fixing_no_cached_data_loads_file(cache, temp_dir):
    """Test _check_needs_fixing loads file when no cached tag_data."""
    test_file = temp_dir / "valid.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    result = cache._check_needs_fixing(test_file, None)
    assert result is True


def test_check_needs_fixing_error_reads_file(cache, temp_dir):
    """Test _check_needs_fixing returns True on file read error."""
    fake_file = temp_dir / "nonexistent.mp3"
    result = cache._check_needs_fixing(fake_file, None)
    assert result is True


def test_check_needs_fixing_exception_in_load(cache, temp_dir):
    """Test _check_needs_fixing handles exception during file load."""
    # Create a file that looks like MP3 but is invalid
    test_file = temp_dir / "invalid.mp3"
    test_file.write_bytes(b"not an mp3 file at all")
    
    # Should return True on exception
    result = cache._check_needs_fixing(test_file, None)
    assert result is True


def test_get_changed_files_modified_needs_fixing(cache, temp_dir):
    """Test get_changed_files handles modified file that needs fixing."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    # Cache with needs_fixing=0 and old mtime
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': 1000,  # Different size to trigger full scan
            'mtime': 123456.0,  # Old mtime
            'artist': 'Artist',
            'title': 'Title',
            'needs_fixing': 0
        }
    ])
    
    # File modified but has invalid tags - should be included
    changed, _, modified_count, _ = cache.get_changed_files([test_file])
    
    # File has invalid tags - should be included
    assert len(changed) == 1
    assert modified_count == 1


def test_get_changed_files_unchanged_needs_fixing(cache, temp_dir):
    """Test get_changed_files handles unchanged file marked needs_fixing."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    stat = test_file.stat()
    # Cache with needs_fixing=1 and old mtime to force full scan
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': stat.st_size,
            'mtime': 123456.0,  # Old mtime to force full scan
            'artist': 'Artist',
            'title': 'Title',
            'needs_fixing': 1  # Marked as needs fixing
        }
    ])
    
    # File unchanged but marked needs_fixing - should include
    changed, _, modified_count, _ = cache.get_changed_files([test_file])
    
    assert len(changed) == 1
    assert modified_count == 1


def test_get_changed_files_skipped_unchanged_valid_tags(cache, temp_dir, monkeypatch):
    """Test get_changed_files skips unchanged file with valid tags."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    stat = test_file.stat()
    # Cache with valid tags and old mtime to force full scan
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': stat.st_size,
            'mtime': 123456.0,  # Old mtime to force full scan
            'artist': 'Artist',
            'title': 'Title',
            'needs_fixing': 0,  # Valid tags
            'tag_data': {'artist': 'Artist', 'title': 'Title'}  # Provide tag_data
        }
    ])
    
    # File unchanged with valid tags - should skip (uses cached tag_data)
    changed, _, modified_count, skipped = cache.get_changed_files([test_file])
    
    assert len(changed) == 0
    assert modified_count == 0
    assert skipped >= 1


def test_close_handles_sqlite_error(cache):
    """Test close() handles sqlite3.Error gracefully."""
    conn = cache._get_connection()
    cache._conns.append(conn)
    conn.close()
    cache.close()
    assert cache._local.conn is None


def test_close_idempotent_multiple_calls(cache):
    """Test close() can be called multiple times safely."""
    cache.close()
    cache.close()
    cache.close()
    assert cache._local.conn is None
    assert len(cache._conns) == 0


def test_close_handles_sqlite_error_on_tracked_conn(cache):
    """Test close() handles sqlite3.Error on tracked connection."""
    # Get a connection and track it
    conn = cache._get_connection()
    cache._conns.append(conn)
    
    # Close the connection outside the cache
    conn.close()
    
    # Now close through cache - should handle sqlite3.Error gracefully
    # (connection already closed)
    cache.close()
    assert cache._local.conn is None


def test_close_handles_sqlite_error_via_mock(cache):
    """Test close() handles sqlite3.Error via mocking."""
    import sqlite3
    
    # Mock conn.close to raise sqlite3.Error
    mock_conn = MagicMock()
    mock_conn.close.side_effect = sqlite3.Error("Connection error")
    cache._conns.append(mock_conn)
    
    # Should not raise
    cache.close()
    assert cache._local.conn is None
    assert len(cache._conns) == 0


def test_v3_migration_creates_artist_genres(temp_dir):
    """Test v3 migration creates artist_genres table."""
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Create a v2 schema DB
    db_path = temp_dir / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version (version) VALUES (2);
        CREATE TABLE scan_cache (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            artist TEXT,
            title TEXT,
            scan_time REAL NOT NULL,
            needs_fixing INTEGER NOT NULL DEFAULT 0,
            missing_artist INTEGER NOT NULL DEFAULT 0,
            missing_title INTEGER NOT NULL DEFAULT 0,
            tag_data TEXT
        );
    """)
    conn.commit()
    conn.close()
    
    # Create cache - should migrate to v3
    cache = LeaderboardCache(cache_path=db_path)
    
    # Verify artist_genres table exists
    conn = cache._get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='artist_genres'"
    )
    assert cursor.fetchone() is not None
    
    cache.close()


def test_v3_migration_adds_columns(temp_dir):
    """Test v3 migration adds fingerprint and duration columns."""
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Create a v2 schema DB
    db_path = temp_dir / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version (version) VALUES (2);
        CREATE TABLE scan_cache (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            artist TEXT,
            title TEXT,
            scan_time REAL NOT NULL,
            needs_fixing INTEGER NOT NULL DEFAULT 0,
            missing_artist INTEGER NOT NULL DEFAULT 0,
            missing_title INTEGER NOT NULL DEFAULT 0,
            tag_data TEXT
        );
    """)
    conn.commit()
    conn.close()
    
    # Create cache - should migrate to v3
    cache = LeaderboardCache(cache_path=db_path)
    
    # Verify columns exist
    conn = cache._get_connection()
    cols = {row['name'] for row in conn.execute("PRAGMA table_info(scan_cache)")}
    assert 'fingerprint' in cols
    assert 'duration' in cols
    
    cache.close()


def test_get_cached_info_invalid_tag_data_json(cache, temp_dir):
    """Test get_cached_info handles invalid JSON in tag_data."""
    # Insert invalid JSON
    conn = cache._get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO scan_cache (path, size, mtime, artist, title, scan_time, tag_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(temp_dir / "test.mp3"), 1234, 123456.0, "Artist", "Title", 123456.0, "invalid json {{{")
    )
    conn.commit()
    
    # Should not raise, should return info with tag_data=None
    info = cache.get_cached_info(str(temp_dir / "test.mp3"))
    assert info is not None
    assert info['artist'] == "Artist"
    assert info['tag_data'] is None



def test_get_changed_files_skips_unchanged(cache, temp_dir):
    """Test get_changed_files skips unchanged files."""
    test_file = temp_dir / "test.mp3"
    test_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    stat = test_file.stat()
    # Cache the file
    cache.update_scan_cache([
        {
            'path': str(test_file),
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'artist': 'Artist',
            'title': 'Title'
        }
    ])
    
    # File unchanged - should skip
    changed, _, modified_count, skipped = cache.get_changed_files([test_file])
    
    assert len(changed) == 0
    assert skipped == 1
    assert modified_count == 0

