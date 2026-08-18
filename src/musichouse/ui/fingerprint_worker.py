"""QThread worker for fingerprinting MP3 files in batches."""

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from musichouse.fingerprint import compute_fingerprint, FingerprintError, is_fpcalc_available
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse import log_setup as logging

logger = logging.get_logger(__name__)


class FingerprintWorker(QThread):
    """Worker thread that fingerprints MP3 files using Chromaprint.
    
    Reads all files from the cache, computes fingerprints for those missing them,
    and writes results back to the cache. Emits progress signals for UI updates.
    """
    
    progress = pyqtSignal(str)  # status message
    file_done = pyqtSignal(int)  # count of files fingerprinted so far
    fingerprint_finished = pyqtSignal(int)  # total files fingerprinted
    error = pyqtSignal(str)  # error message
    
    def __init__(self, cache: LeaderboardCache, parent=None):
        """Initialize the worker.
        
        Args:
            cache: LeaderboardCache instance for reading/writing fingerprints.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._cache = cache
        self._stop_flag = False
        self._fingerprinted_count = 0
    
    def stop(self):
        """Request stop of the worker. Called from GUI thread."""
        self._stop_flag = True
    
    def run(self):
        """Main loop: fingerprint all files missing fingerprints."""
        if not is_fpcalc_available():
            self.error.emit("fpcalc not available. Install libchromaprint-tools.")
            self.fingerprint_finished.emit(0)
            return
        
        paths = self._cache.get_all_scanned_paths()
        
        for path_str in paths:
            if self._stop_flag:
                logger.info("FingerprintWorker stopped by user")
                break
            
            path = Path(path_str)
            self.progress.emit(f"Fingerprinting: {path.name}")
            
            # Check if already has fingerprint
            existing_fp, existing_duration = self._cache.get_fingerprint(path_str)
            if existing_fp is not None:
                logger.debug(f"Skipping {path.name}: already fingerprinted")
                continue
            
            try:
                fingerprint_bytes, duration = compute_fingerprint(path_str)
                self._cache.set_fingerprint(path_str, fingerprint_bytes, duration)
                self._fingerprinted_count += 1
                self.file_done.emit(self._fingerprinted_count)
                logger.info(f"Fingerprinted: {path.name} ({duration:.1f}s)")
            except FingerprintError as e:
                self.progress.emit(f"Error fingerprinting {path.name}: {e}")
                logger.warning(f"Failed to fingerprint {path.name}: {e}")
                # Continue with next file
    
        self.fingerprint_finished.emit(self._fingerprinted_count)
        logger.info(f"FingerprintWorker completed: {self._fingerprinted_count} files fingerprinted")