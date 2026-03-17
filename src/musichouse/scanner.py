"""Scanner module for MusicHouse."""

import os
from pathlib import Path
from typing import List, Tuple, Callable, Optional

from musichouse import logging

logger = logging.get_logger(__name__)


class MP3Scanner:
    """Scans directories recursively for MP3 files."""

    def __init__(self, base_path: Path):
        """Initialize the scanner.
        
        Args:
            base_path: The root directory to scan.
        """
        self.base_path = base_path
        self._results: List[Path] = []
        self._errors: List[Tuple[Path, str]] = []
        self._current_directory: Optional[Path] = None
        self._file_count: int = 0
        self._progress_callback: Optional[Callable[[str], None]] = None
        self._file_callback: Optional[Callable[[int], None]] = None
        self._file_callback_batch_size: int = 100
        self._stop_requested: bool = False  # Flag to stop scan

    def scan(self) -> List[Path]:
        """Scan the directory for MP3 files.
        
        Returns:
            List of paths to MP3 files found.
        """
        self._results = []
        self._errors = []
        self._file_count = 0
        
        try:
            for root, dirs, files in os.walk(self.base_path):
                # Check for stop request
                if self._stop_requested:
                    logger.info("Scan stopped by user")
                    break
                
                self._current_directory = Path(root)
                
                # Emit progress update
                if self._progress_callback:
                    self._progress_callback(str(Path(root)))
                
                for filename in files:
                    # Check for stop request
                    if self._stop_requested:
                        logger.info("Scan stopped by user")
                        break
                    
                    if filename.lower().endswith('.mp3'):
                        file_path = Path(root) / filename
                        self._results.append(file_path)
                        self._file_count += 1
                        
                        # Call file_callback every batch_size files
                        if (self._file_callback and
                            self._file_count % self._file_callback_batch_size == 0):
                            self._file_callback(self._file_count)
                            
        except OSError as e:
            self._errors.append((self.base_path, str(e)))
            logger.warning(f"Could not access directory {self.base_path}: {e}")
        
        # Final callback for incomplete last batch
        if (self._file_callback and 
            self._file_count > 0 and 
            self._file_count % 100 != 0):
            self._file_callback(self._file_count)
        
        return self._results.copy()

    def get_results(self) -> List[Path]:
        """Get the scan results."""
        return self._results.copy()

    def get_errors(self) -> List[Tuple[Path, str]]:
        """Get any errors encountered during scanning."""
        return self._errors.copy()

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for directory progress updates."""
        self._progress_callback = callback
    
    def set_file_callback(
        self, 
        callback: Callable[[int], None], 
        batch_size: int = 100
    ) -> None:
        """Set callback for file count updates.
        
        Args:
            callback: Function to call with file count
            batch_size: Number of files between callbacks (default 100)
        """
        self._file_callback = callback
        self._file_callback_batch_size = batch_size
    
    def get_file_count(self) -> int:
        """Get the number of files processed."""
        return self._file_count
    
    def stop(self) -> None:
        """Request to stop the scan."""
        self._stop_requested = True
        logger.info("Scan stop requested")
    
    def is_stopped(self) -> bool:
        """Check if stop was requested."""
        return self._stop_requested
