"""SQLite cache for leaderboard data."""

import sqlite3
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Dict

from musichouse.utils import load_mp3_safely
from musichouse import logging

logger = logging.get_logger(__name__)


class LeaderboardCache:
    """SQLite-based cache for leaderboard data."""

    DB_SCHEMA = """
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
        suggested_title TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_artists_count ON artists(count DESC);
    CREATE INDEX IF NOT EXISTS idx_scan_cache_mtime ON scan_cache(mtime);
    """

    def __init__(self, cache_path: Optional[Path] = None):
        """Initialize the leaderboard cache.
        
        Args:
            cache_path: Path to SQLite database file or directory.
        """
        if cache_path is None:
            from musichouse import config
            cache_path = config.get_config_dir() / "leaderboard.db"
        elif cache_path.is_dir():
            cache_path = cache_path / "leaderboard.db"
        
        self.cache_path = cache_path
        self._local = threading.local()  # Thread-local connections
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
            
            # Performance optimizations
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA busy_timeout=5000;")
            self._local.conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn.execute("PRAGMA cache_size=-20000;")  # 20MB
            self._local.conn.execute("PRAGMA temp_store=MEMORY;")
        
        return self._local.conn

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        conn = self._get_connection()
        conn.executescript(self.DB_SCHEMA)

    def update_artists(self, artist_counts: dict) -> None:
        """Update artist counts in database.
        
        Args:
            artist_counts: Dict mapping artist name to count.
        """
        conn = self._get_connection()
        
        for artist, count in artist_counts.items():
            conn.execute(
                """INSERT INTO artists (name, count) 
                   VALUES (?, ?) 
                   ON CONFLICT(name) DO UPDATE SET count = count + ?""",
                (artist, count, count)
            )

    def get_top_artists(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top N artists by count."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT name, count FROM artists ORDER BY count DESC LIMIT ?",
            (limit,)
        )
        return [(row['name'], row['count']) for row in cursor.fetchall()]

    def get_all_artists(self) -> List[Tuple[str, int]]:
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

    def get_cached_info(self, path: str) -> Optional[Dict]:
        """Get cached scan info for a file.
        
        Args:
            path: File path string.
            
        Returns:
            Dict with size, mtime, artist, title if cached, None otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT path, size, mtime, artist, title, scan_time, needs_fixing, missing_artist, missing_title FROM scan_cache WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'path': row['path'],
                'size': row['size'],
                'mtime': row['mtime'],
                'artist': row['artist'],
                'title': row['title'],
                'scan_time': row['scan_time'],
                'needs_fixing': row['needs_fixing'],
                'missing_artist': row['missing_artist'],
                'missing_title': row['missing_title']
            }
        return None

    def update_scan_cache(self, files_info: list) -> None:
        """Update scan cache with file info.
        
        Args:
            files_info: List of dicts with path, size, mtime, artist, title,
                        needs_fixing, missing_artist, missing_title,
                        suggested_artist, suggested_title.
        """
        conn = self._get_connection()
        import time
        scan_time = time.time()
        
        for info in files_info:
            conn.execute(
                """INSERT OR REPLACE INTO scan_cache
                   (path, size, mtime, artist, title, scan_time,
                    needs_fixing, missing_artist, missing_title,
                    suggested_artist, suggested_title)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (info['path'], info['size'], info['mtime'],
                 info.get('artist'), info.get('title'), scan_time,
                 info.get('needs_fixing', 0), info.get('missing_artist', 0),
                 info.get('missing_title', 0), info.get('suggested_artist'),
                 info.get('suggested_title'))
            )

    def get_changed_files(self, base_path: Path) -> Tuple[list, int, int, int]:
        """Get files that need processing (new or modified).
        
        Args:
            base_path: Base directory path.
            
        Returns:
            Tuple of (changed_files, new_count, modified_count, skipped_count)
        """
        import os
        
        changed_files = []
        new_count = 0
        modified_count = 0
        skipped_count = 0
        
        for root, dirs, files in os.walk(base_path):
            for filename in files:
                if filename.lower().endswith('.mp3'):
                    file_path = Path(root) / filename
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
                    
                    cached = self.get_cached_info(path_str)
                    
                    if cached is None:
                        # New file - always include
                        changed_files.append(file_path)
                        new_count += 1
                    elif cached['size'] != size or cached['mtime'] != mtime:
                        # Modified file - check if it needs fixing
                        needs_fixing = self._check_needs_fixing(file_path)
                        if needs_fixing:
                            changed_files.append(file_path)
                            modified_count += 1
                        else:
                            skipped_count += 1
                    elif cached['needs_fixing']:
                        # Unchanged file but marked as needing fixing in DB
                        # This handles files that were cached with needs_fixing=1
                        # but mtime/size haven't changed yet
                        changed_files.append(file_path)
                        modified_count += 1
                    else:
                        # Unchanged file with no needs_fixing flag - skip
                        skipped_count += 1
        
        return changed_files, new_count, modified_count, skipped_count

    def _check_needs_fixing(self, file_path: Path) -> bool:
        """Check if a file needs fixing by verifying ID3 tag correctness.
        
        Args:
            file_path: Path to the MP3 file.
            
        Returns:
            True if file is missing required tags (artist or title),
            or if file cannot be read (corrupted/invalid MP3).
            False if file has valid tags (artist and title are set).
        """
        try:
            audiofile = load_mp3_safely(file_path)
            if audiofile is None or audiofile.tag is None:
                # Can't read file or no tags - treat as needing fixing
                return True
            
            existing_artist = getattr(audiofile.tag, 'artist', None) or ''
            existing_title = getattr(audiofile.tag, 'title', None) or ''
            
            return not existing_artist or not existing_title
        except Exception:
            # On any error reading the file, assume it needs fixing
            return True

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
