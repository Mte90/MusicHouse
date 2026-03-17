"""Utility functions for MusicHouse."""

import sys
import os
import io
from pathlib import Path
from typing import Optional
import logging

import eyed3

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
    """
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
                logger.error(f"eyed3 stderr for {file_path}: {stderr_output}")
                
    except Exception as e:
        logger.error(f"Error loading MP3 {file_path}: {e}")
        return None
