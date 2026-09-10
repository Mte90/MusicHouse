"""QThread worker for tag writes to prevent UI freezing."""

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from musichouse import config
from musichouse import log_setup as logging
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.tag_writer import write_tags

logger = logging.get_logger(__name__)


class TagFixWorker(QThread):
    """Worker thread for writing tags to multiple files.
    
    Emits signals for progress, file completion, and final results.
    """
    
    # Signals
    progress = pyqtSignal(int, str)  # (file index, filename)
    file_fixed = pyqtSignal(str, bool, str)  # (file_path, success, filename)
    failures = pyqtSignal(list)  # list of (filename, error_type, error_message) tuples
    finished = pyqtSignal(int, int)  # (success count, failure count)
    
    def __init__(self, files_data: list[dict], auto_fix: bool = False):
        """Initialize the worker.
        
        Args:
            files_data: List of file entry dicts with 'path', 'suggested_artist', 'suggested_title'.
            auto_fix: If True, use suggested values for all files. If False, use table values.
        """
        super().__init__()
        self._files_data = files_data
        self._auto_fix = auto_fix
        self._cancelled = False
        
    def cancel(self):
        """Request cancellation of the worker."""
        self._cancelled = True
        
    def run(self):
        """Execute the tag writing in the worker thread."""
        success_count = 0
        failure_count = 0
        failure_list = []  # List of (filename, error_type, error_message) tuples
        
        # Create cache once for the entire batch (Fix M5)
        cache = LeaderboardCache(config.get_config_dir())
        
        try:
            for idx, entry in enumerate(self._files_data):
                if self._cancelled:
                    logger.info("TagFixWorker cancelled by user")
                    break
                    
                file_path = entry["path"]
                if isinstance(file_path, str):
                    file_path = Path(file_path)
                
                # Emit progress signal
                self.progress.emit(idx, file_path.name)
                
                # Get artist/title from entry (current values from table, or suggested as fallback)
                new_artist = entry.get("current_artist", entry["suggested_artist"])
                new_title = entry.get("current_title", entry["suggested_title"])
                
                # Check cache to avoid redundant eyed3.load()
                cached_info = cache.get_cached_info(str(file_path))
                
                # Initialize error to None (Fix M6)
                error: Exception | None = None
                
                # If cached tag data exists and already matches target, skip write
                if cached_info and cached_info.get('tag_data'):
                    cached_artist = cached_info['tag_data'].get('artist', '') or ''
                    cached_title = cached_info['tag_data'].get('title', '') or ''
                    if cached_artist == new_artist and cached_title == new_title:
                        # Tags already match - skip redundant write
                        success = True
                        logger.info(f"Cached tags match target, skipping write: {file_path.name}")
                    else:
                        # Tags differ - need to write (cache will be updated after)
                        success = write_tags(file_path, new_artist, new_title, force=True)
                else:
                    # No cached tag data - must load file with eyed3
                    success = write_tags(file_path, new_artist, new_title, force=True)
                
                if success:
                    success_count += 1
                    self.file_fixed.emit(str(file_path), True, file_path.name)
                    # Log already fixed only if we skipped due to cache match
                    if cached_info and cached_info.get('tag_data'):
                        cached_artist = cached_info['tag_data'].get('artist', '') or ''
                        cached_title = cached_info['tag_data'].get('title', '') or ''
                        if cached_artist == new_artist and cached_title == new_title:
                            logger.info(f"Already fixed (cached): {file_path.name}")
                        else:
                            logger.info(f"Fixed: {file_path.name}")
                    else:
                        logger.info(f"Fixed: {file_path.name}")
                else:
                    failure_count += 1
                    self.file_fixed.emit(str(file_path), False, file_path.name)
                    
                    # Guard against unbound error (Fix M6)
                    error_type = type(error).__name__ if error else "Unknown"
                    error_msg = str(error) if error else "Unknown error"
                    failure_list.append((file_path.name, error_type, error_msg))
                    logger.error(f"Failed to fix: {file_path.name} - {error_type}: {error_msg}")
        
        except Exception as e:
            # Top-level exception handler (Fix C2)
            logger.exception("Unexpected error in TagFixWorker")
            # Count remaining files as failures
            remaining = len(self._files_data) - success_count - failure_count
            failure_count += remaining
            for i in range(remaining):
                if idx + i < len(self._files_data):
                    entry = self._files_data[idx + i]
                    file_path = entry["path"]
                    if isinstance(file_path, str):
                        file_path = Path(file_path)
                    
                    failure_list.append((file_path.name, type(e).__name__, str(e)))
        
        finally:
            # Always emit finished signal (Fix C2)
            if failure_list:
                self.failures.emit(failure_list)
            self.finished.emit(success_count, failure_count)
            logger.info(f"TagFixWorker completed: {success_count} success, {failure_count} failures")
            # Close cache connection (Fix M5)
            cache.close()


class TagUpdateWorker(QThread):
    """Worker thread for updating database after tag fixes.
    
    This separates DB I/O from the main tag writing worker.
    """
    
    finished = pyqtSignal()
    
    def __init__(self, fixed_paths: list[Path]):
        """Initialize the worker.
        
        Args:
            fixed_paths: List of file paths that were successfully fixed.
        """
        super().__init__()
        self._fixed_paths = fixed_paths
        
    def run(self):
        """Update database to mark files as fixed."""
        try:
            cache = LeaderboardCache(config.get_config_dir())
            conn = cache._get_connection()
            
            for path in self._fixed_paths:
                conn.execute(
                    "UPDATE scan_cache SET needs_fixing = 0, missing_artist = 0, missing_title = 0 WHERE path = ?",
                    (str(path),)
                )
            
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cache.close()
            logger.info(f"Updated DB for {len(self._fixed_paths)} fixed files")
            
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error updating DB after fix: {e}")
        
        self.finished.emit()
