"""SQLite cache for leaderboard data."""

import os
import sqlite3
import threading
import time
from pathlib import Path

from musichouse import log_setup as logging
from musichouse.utils import load_mp3_safely

logger = logging.get_logger(__name__)


class LeaderboardCache:
    """SQLite-based cache for leaderboard data."""

    DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);
    
    CREATE TABLE IF NOT EXISTS artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        count INTEGER NOT NULL DEFAULT 0
    );
    
    CREATE TABLE IF NOT EXISTS similar_artists (
        artist_name TEXT PRIMARY KEY,
        similar_json TEXT NOT NULL,
        last_updated INTEGER NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS scan_cache (
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
        tag_data TEXT,
        fingerprint BLOB,
        duration REAL
    );
    
    CREATE INDEX IF NOT EXISTS idx_artists_count ON artists(count DESC);
    CREATE INDEX IF NOT EXISTS idx_scan_cache_mtime ON scan_cache(mtime);
    
    CREATE TABLE IF NOT EXISTS artist_genres (
        artist_name TEXT PRIMARY KEY,
        genres_json TEXT NOT NULL,
        last_updated INTEGER NOT NULL
    );
    """

    def __init__(self, cache_path: Path | None = None):
        """Initialize the leaderboard cache.
        
        Args:
            cache_path: Path to SQLite database file or directory.
        """
        from pathlib import Path
        
        if cache_path is None:
            from musichouse import config
            cache_path = config.get_config_dir() / "leaderboard.db"
        else:
            cache_path = Path(cache_path) if isinstance(cache_path, str) else cache_path
            if cache_path.is_dir():
                cache_path = cache_path / "leaderboard.db"
        
        self.cache_path = cache_path
        self._local = threading.local()  # Thread-local connections
        self._conns: list[sqlite3.Connection] = []  # Track all connections for cleanup
        # Note: SQLite automatically manages WAL files (.db-shm, .db-wal)
        # No need to check for stale files - SQLite handles this automatically
        
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.cache_path,
                timeout=5.0,  # 5 second timeout
                check_same_thread=False,
                isolation_level=None,  # Autocommit mode
            )
            self._local.conn.row_factory = sqlite3.Row
            
            # Track connection for cleanup
            self._conns.append(self._local.conn)
            
            # Performance optimizations
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA busy_timeout=5000;")
            self._local.conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn.execute("PRAGMA cache_size=-20000;")  # 20MB
            self._local.conn.execute("PRAGMA temp_store=MEMORY;")
        
        return self._local.conn

    def _ensure_db(self) -> None:
        """Ensure database and tables exist, migrating old schemas."""
        conn = self._get_connection()
        conn.executescript(self.DB_SCHEMA)
        
        # Get current schema version
        cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0
        
        # Migration v2: add tag_data column
        if current_version < 2:
            cols = {row['name'] for row in conn.execute("PRAGMA table_info(scan_cache)")}
            if 'tag_data' not in cols:
                conn.execute("ALTER TABLE scan_cache ADD COLUMN tag_data TEXT")
                logger.info("Migrated scan_cache: added tag_data column")
            conn.execute("UPDATE schema_version SET version = 2")
            conn.commit()
            logger.info("Updated schema version to 2")
        
        # Migration v3: add fingerprint and duration columns, create artist_genres table
        if current_version < 3:
            cols = {row['name'] for row in conn.execute("PRAGMA table_info(scan_cache)")}
            if 'fingerprint' not in cols:
                conn.execute("ALTER TABLE scan_cache ADD COLUMN fingerprint BLOB")
                logger.info("Migrated scan_cache: added fingerprint column")
            if 'duration' not in cols:
                conn.execute("ALTER TABLE scan_cache ADD COLUMN duration REAL")
                logger.info("Migrated scan_cache: added duration column")
            
            # Create artist_genres table if it doesn't exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='artist_genres'"
            )
            if cursor.fetchone() is None:
                conn.execute(
                    """CREATE TABLE artist_genres (
                        artist_name TEXT PRIMARY KEY,
                        genres_json TEXT NOT NULL,
                        last_updated INTEGER NOT NULL
                    )"""
                )
                logger.info("Created artist_genres table")
            
            conn.execute("UPDATE schema_version SET version = 3")
            conn.commit()
            logger.info("Updated schema version to 3")
        
        # Initialize schema version if missing (fresh DB)
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (3)")
            conn.commit()
            logger.info("Created schema_version table, set to version 3")

    def update_artists(self, artist_counts: dict) -> None:
        """Update artist counts in database using bulk insert.
        
        Args:
            artist_counts: Dict mapping artist name to count.
        """
        conn = self._get_connection()
        
        # Bulk insert with executemany for single transaction
        data = [(artist, count, count) for artist, count in artist_counts.items()]
        conn.executemany(
            """INSERT INTO artists (name, count) 
               VALUES (?, ?) 
               ON CONFLICT(name) DO UPDATE SET count = ?""",
            data
        )
        conn.commit()

    def get_top_artists(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get top N artists by count."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT name, count FROM artists ORDER BY count DESC LIMIT ?",
            (limit,)
        )
        return [(row['name'], row['count']) for row in cursor.fetchall()]

    def get_all_artists(self) -> list[tuple[str, int]]:
        """Get all artists sorted by count."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT name, count FROM artists ORDER BY count DESC"
        )
        return [(row['name'], row['count']) for row in cursor.fetchall()]

    def clear(self) -> None:
        """Clear all data from cache."""
        conn = self._get_connection()
        conn.execute("DELETE FROM artists")
        conn.execute("DELETE FROM similar_artists")
        conn.execute("DELETE FROM scan_cache")

    def get_cached_info(self, path: str) -> dict | None:
        """Get cached scan info for a file.
        
        Args:
            path: File path string.
            
        Returns:
            Dict with size, mtime, artist, title, tag_data if cached, None otherwise.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT path, size, mtime, artist, title, scan_time, needs_fixing, missing_artist, missing_title, tag_data FROM scan_cache WHERE path = ?",
                (path,)
            )
        except sqlite3.OperationalError:
            # Column tag_data doesn't exist (old schema)
            cursor = conn.execute(
                "SELECT path, size, mtime, artist, title, scan_time, needs_fixing, missing_artist, missing_title FROM scan_cache WHERE path = ?",
                (path,)
            )
        row = cursor.fetchone()
        if row:
            import json
            tag_data = None
            if row['tag_data']:
                try:
                    tag_data = json.loads(row['tag_data'])
                except (json.JSONDecodeError, TypeError):
                    pass
            return {
                'path': row['path'],
                'size': row['size'],
                'mtime': row['mtime'],
                'artist': row['artist'],
                'title': row['title'],
                'scan_time': row['scan_time'],
                'needs_fixing': row['needs_fixing'],
                'missing_artist': row['missing_artist'],
                'missing_title': row['missing_title'],
                'tag_data': tag_data
            }
        return None

    def get_fingerprint(self, path: str) -> tuple[bytes | None, float | None]:
        """Get fingerprint and duration for a file from scan_cache.
        
        Args:
            path: File path string.
            
        Returns:
            Tuple of (fingerprint, duration) if set, (None, None) otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT fingerprint, duration FROM scan_cache WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        if row:
            return (row['fingerprint'], row['duration'])
        return (None, None)

    def set_fingerprint(self, path: str, fingerprint: bytes, duration: float) -> None:
        """Set fingerprint and duration for a file in scan_cache.
        
        Args:
            path: File path string.
            fingerprint: Fingerprint bytes.
            duration: Duration in seconds.
        """
        conn = self._get_connection()
        conn.execute(
            """UPDATE scan_cache SET fingerprint = ?, duration = ? WHERE path = ?""",
            (fingerprint, duration, path)
        )
        conn.commit()

    def get_all_scanned_paths(self) -> list[str]:
        """Get all file paths from scan_cache.
        
        Returns:
            List of file path strings.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT path FROM scan_cache")
        return [row['path'] for row in cursor.fetchall()]

    def get_artist_genres(self, artist_name: str) -> list[str] | None:
        """Get cached genres for an artist.
        
        Args:
            artist_name: Name of the artist.
            
        Returns:
            List of genres if cached, None otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT genres_json FROM artist_genres WHERE artist_name = ?",
            (artist_name,)
        )
        row = cursor.fetchone()
        if row and row['genres_json']:
            import json
            try:
                return json.loads(row['genres_json'])
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def set_artist_genres(self, artist_name: str, genres: list[str]) -> None:
        """Cache genres for an artist.
        
        Args:
            artist_name: Name of the artist.
            genres: List of genre strings.
        """
        conn = self._get_connection()
        import json
        conn.execute(
            """INSERT OR REPLACE INTO artist_genres (artist_name, genres_json, last_updated)
               VALUES (?, ?, ?)""",
            (artist_name, json.dumps(genres), int(time.time()))
        )
        conn.commit()

    def get_similar_artists(self, seed: str) -> list[dict]:
        """Get cached similar artists for a seed.
        
        Args:
            seed: Seed artist name.
            
        Returns:
            List of dicts with "artist" and "reason" keys, or empty list if none cached.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT similar_json FROM similar_artists WHERE artist_name = ?",
            (seed,)
        )
        row = cursor.fetchone()
        if row and row['similar_json']:
            import json
            try:
                return json.loads(row['similar_json'])
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def save_similar_artists(self, seed: str, suggestions: list[dict]) -> None:
        """Save similar artists for a seed (replaces all existing).
        
        Args:
            seed: Seed artist name.
            suggestions: List of dicts with "artist" and "reason" keys.
        """
        import json
        conn = self._get_connection()
        # REPLACE-all semantics: delete existing, then insert new
        conn.execute(
            "DELETE FROM similar_artists WHERE artist_name = ?",
            (seed,)
        )
        conn.execute(
            """INSERT INTO similar_artists (artist_name, similar_json, last_updated)
               VALUES (?, ?, ?)""",
            (seed, json.dumps(suggestions), int(time.time()))
        )
        conn.commit()

    def get_all_indexed_artists(self) -> list[str]:
        """Get distinct artist names from scan_cache.
        
        Returns:
            List of unique artist strings (excluding None/empty).
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT DISTINCT artist FROM scan_cache WHERE artist IS NOT NULL AND artist != ''"
        )
        return [row['artist'] for row in cursor.fetchall() if row['artist']]

    def update_scan_cache(self, files_info: list) -> None:
        """Update scan cache with file info.
        
        Args:
            files_info: List of dicts with path, size, mtime, artist, title,
                        needs_fixing, missing_artist, missing_title,
                        suggested_artist, suggested_title, tag_data.
        """
        conn = self._get_connection()
        import json
        scan_time = time.time()
        
        for info in files_info:
            # Convert None to NULL for database
            artist = info.get('artist')
            title = info.get('title')
            suggested_artist = info.get('suggested_artist')
            suggested_title = info.get('suggested_title')
            tag_data = info.get('tag_data')
            
            # Serialize tag_data to JSON if present
            tag_data_json = None
            if tag_data is not None:
                try:
                    tag_data_json = json.dumps(tag_data)
                except (TypeError, ValueError):
                    pass
            
            conn.execute(
                """INSERT OR REPLACE INTO scan_cache
                   (path, size, mtime, artist, title, scan_time,
                    needs_fixing, missing_artist, missing_title,
                    suggested_artist, suggested_title, tag_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (info['path'], info['size'], info['mtime'],
                 artist if artist is not None else None,
                 title if title is not None else None, scan_time,
                 info.get('needs_fixing', 0), info.get('missing_artist', 0),
                 info.get('missing_title', 0),
                 suggested_artist if suggested_artist is not None else None,
                 suggested_title if suggested_title is not None else None,
                 tag_data_json)
            )
    def get_changed_files(self, files: list[Path]) -> tuple[list, int, int, int]:
        """Filter files that have changed since last scan.
        
        Args:
            files: List of files from MP3Scanner.scan() (already walked).
            
        Returns:
            Tuple of (changed_files, new_count, modified_count, skipped_count)
        """
        start_time = time.perf_counter()
        
        # Quick no-op check: compare cache's max mtime with tree's max mtime
        conn = self._get_connection()
        
        # Get the base directory from the first file
        if not files:
            return [], 0, 0, 0
        
        base_dir = files[0].parent
        prefix = f"{base_dir}%"
        
        cursor = conn.execute("SELECT MAX(mtime) FROM scan_cache WHERE path LIKE ?", (prefix,))
        row = cursor.fetchone()
        cache_max_mtime = row[0] if row and row[0] else 0
        
        # Quick scandir to find newest mtime in the tree
        tree_max_mtime = 0
        if cache_max_mtime > 0:
            try:
                for entry in os.scandir(base_dir):
                    if entry.is_file():
                        try:
                            stat = entry.stat()
                            tree_max_mtime = max(tree_max_mtime, stat.st_mtime)
                        except OSError:
                            pass
            except OSError:
                pass
        
        # If cache has data and cache's max mtime >= tree's max mtime, nothing changed
        # If cache_max is 0, we need full scan (cache is empty or invalid)
        if cache_max_mtime > 0 and cache_max_mtime >= tree_max_mtime:
            duration = time.perf_counter() - start_time
            logger.debug(f"No-op quick check: cache_max={cache_max_mtime}, tree_max={tree_max_mtime}, skipped in {duration*1000:.1f}ms")
            return [], 0, 0, len(files)
        
        # Full scan needed
        cursor = conn.execute("SELECT path, mtime, size, needs_fixing FROM scan_cache")
        cached = {Path(row[0]): {'mtime': row[1], 'size': row[2], 'needs_fixing': row[3]} for row in cursor.fetchall()}
        
        changed_files = []
        new_count = 0
        modified_count = 0
        skipped_count = 0
        
        for file_path in files:
            path_str = str(file_path)
            
            try:
                stat = file_path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                # Can't access file, treat as changed
                changed_files.append(file_path)
                new_count += 1
                continue
            
            cached_info = cached.get(file_path)
            
            if cached_info is None:
                # New file - always include
                changed_files.append(file_path)
                new_count += 1
            elif cached_info['size'] != size or cached_info['mtime'] != mtime:
                # Modified file - check if it needs fixing
                # Pass cached info to avoid reloading if tag_data exists
                needs_fixing = self._check_needs_fixing(file_path, self.get_cached_info(path_str))
                if needs_fixing:
                    changed_files.append(file_path)
                    modified_count += 1
                else:
                    skipped_count += 1
            elif cached_info['needs_fixing']:
                # Unchanged file but marked as needing fixing in DB
                # This handles files that were cached with needs_fixing=1
                # but mtime/size haven't changed yet
                changed_files.append(file_path)
                modified_count += 1
            else:
                # Unchanged file with no needs_fixing flag - skip
                skipped_count += 1
        
        duration = time.perf_counter() - start_time
        logger.info(f"get_changed_files: {len(changed_files)} changed in {duration*1000:.1f}ms")
        return changed_files, new_count, modified_count, skipped_count

    def _check_needs_fixing(self, file_path: Path, cached_info: dict | None = None) -> bool:
        """Check if a file needs fixing by verifying ID3 tag correctness.
        
        Args:
            file_path: Path to the MP3 file.
            cached_info: Optional cached info with tag_data to avoid reload.
            
        Returns:
            True if file is missing required tags (artist or title),
            or if file cannot be read (corrupted/invalid MP3).
            False if file has valid tags (artist and title are set).
        """
        # Use cached tag data if available - avoids redundant eyed3.load()
        if cached_info and cached_info.get('tag_data'):
            tag_data = cached_info['tag_data']
            existing_artist = tag_data.get('artist', '') or ''
            existing_title = tag_data.get('title', '') or ''
            return not existing_artist or not existing_title
        
        # Fallback to loading file if no cached tag data
        try:
            audiofile = load_mp3_safely(file_path)
            if audiofile is None or audiofile.tag is None:
                # Can't read file or no tags - treat as needing fixing
                return True
            
            existing_artist = getattr(audiofile.tag, 'artist', None) or ''
            existing_title = getattr(audiofile.tag, 'title', None) or ''
            
            return not existing_artist or not existing_title
        except Exception:  # noqa: BLE001
            # On any error reading the file, assume it needs fixing
            return True

    def close(self) -> None:
        """Close all database connections. Idempotent - safe to call multiple times."""
        # Close all tracked connections
        for conn in self._conns:
            try:
                if conn is not None:
                    conn.close()
            except sqlite3.Error:
                # Connection may already be closed
                pass
        
        # Clear the current thread's connection
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn = None
        
        # Clear the registry
        self._conns.clear()
    
    def __del__(self) -> None:
        """Best-effort cleanup on garbage collection. Never raise from __del__."""
        try:
            self.close()
        except BaseException:  # noqa: BLE001, S110 - intentional: never raise from __del__
            # Never raise from __del__ - it can cause issues during interpreter shutdown
            pass
