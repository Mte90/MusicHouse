"""Utility modules for MusicHouse."""

import sys
import os
import io
from pathlib import Path
from typing import Optional
import logging

import eyed3

from musichouse.error_handling import CorruptedFileError

logger = logging.getLogger(__name__)


class silence_stderr:
    """Context manager to temporarily silence stderr output."""
    
    def __init__(self):
        self.devnull = open(os.devnull, 'w')
    
    def __enter__(self):
        self.stderr_old = sys.stderr
        sys.stderr = self.devnull
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self.stderr_old
        self.devnull.close()


def load_mp3_safely(file_path: Path) -> Optional["eyed3.AudioFile"]:
    """Load an MP3 file safely with stderr captured.
    
    eyed3 tends to write to stderr for corrupted files.
    This function captures that output for debugging.
    
    Args:
        file_path: Path to the MP3 file to load.
        
    Returns:
        AudioFile object on success, None if file cannot be loaded.
        
    Raises:
        CorruptedFileError: If file is corrupted and cannot be loaded.
    """
    result = None
    try:
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr_capture
        
        try:
            result = eyed3.load(file_path)
            return result
        finally:
            sys.stderr = old_stderr
            stderr_output = stderr_capture.getvalue()
            if stderr_output and result is None:
                # T40: Log file size and header validity for corrupted files
                file_size = file_path.stat().st_size if file_path.exists() else 0
                has_valid_header = file_path.read_bytes(3) == b"ID3" if file_path.exists() and file_path.stat().st_size >= 3 else False
                logger.error(f"eyed3 stderr for {file_path}: {stderr_output}")
                logger.error(f"  File size: {file_size} bytes, Valid ID3 header: {has_valid_header}")
                raise CorruptedFileError(str(file_path), f"Failed to load - size: {file_size}B, valid header: {has_valid_header}")
                
    except CorruptedFileError:
        # Re-raise corrupted file errors
        raise
    except Exception as e:
        logger.error(f"Error loading MP3 {file_path}: {e}")
        return None


from musichouse.utils.lock import SingleInstanceLock

__all__ = ["silence_stderr", "load_mp3_safely", "SingleInstanceLock"]
