"""Filename and folder parsing utilities for MusicHouse."""

import re
from pathlib import Path


def parse_filename(filename: str) -> tuple[str, str]:
    """Parse MP3 filename to extract artist and title.
    
    Handles pattern: "artist - title.mp3" with flexible spacing around hyphen.
    
    Args:
        filename: The filename string (with .mp3 extension).
        
    Returns:
        Tuple of (artist, title) extracted from filename.
    """
    # If no .mp3 extension, return the full name for both
    if not filename.lower().endswith('.mp3'):
        return (filename.strip(), filename.strip())
    
    # Pattern: "artist - title.mp3" with flexible spacing around hyphen or en-dash
    # Handles both regular hyphen (-) and en-dash (–)
    match = re.match(r'^(.+?)\s*[-–]\s*(.+\.mp3)$', filename, re.IGNORECASE)
    if match:
        artist = match.group(1).strip()
        title = match.group(2)[:-4]  # Strip .mp3
        return (artist, title)
    
    # Fallback: split on first hyphen
    if '-' in filename:
        idx = filename.index('-')
        artist = filename[:idx].strip()
        title = filename[idx+1:].strip()
        if title.lower().endswith('.mp3'):
            title = title[:-4]
        return (artist, title)
    # No hyphen found - use parent directory name as artist instead
    # Only happens when filename lacks artist info and has no hyphen
    name = filename
    if name.lower().endswith('.mp3'):
        name = name[:-4]
    
    if not name:
        return ("", "")
    
    # Use parent directory name as artist
    artist_from_folder = "Unknown"
    try:
        # Extract directory name from the filename path info
        # Since we only have filename, we need to get folder name otherwise
        import os
        # Simulate getting folder name - will need actual file path
        # For now return filename as artist (existing behavior)
        return (name.strip(), name.strip())
    except:
        return (name.strip(), name.strip())
    # No hyphen found, strip .mp3 and return full name
    name = filename
    if name.lower().endswith('.mp3'):
        name = name[:-4]
    
    if not name:
        return ("", "")
    
    return (name.strip(), name.strip())


def validate_filename_pattern(filename: str) -> tuple[bool, str, str]:
    """Validate filename matches 'artist - title.mp3' pattern.
    
    Args:
        filename: The filename string (with .mp3 extension).
        
    Returns:
        Tuple of (is_valid, artist, title):
        - is_valid: True if pattern matches AND both artist/title non-empty
        - artist: Extracted artist name (empty if invalid)
        - title: Extracted title (empty if invalid)
    """
    artist, title = parse_filename(filename)
    
    # Must have a hyphen in the filename
    if '-' not in filename:
        return (False, "", "")
    
    # Title should not end with .mp3
    if title.endswith('.mp3'):
        return (False, "", "")
    
    if not artist or not title:
        return (False, "", "")
    
    return (True, artist, title)


def get_artist_from_folder(file_path: Path) -> str:
    """Get artist from parent folder name when filename lacks artist.
    
    Walks up the directory tree until finding a non-empty folder name.
    
    Args:
        file_path: The path to the MP3 file.
        
    Returns:
        The first non-empty parent folder name, or "Unknown" if not found.
    """
    current = file_path.parent
    
    while current != current.parent:
        folder_name = current.name.strip()
        if folder_name:
            return folder_name
        current = current.parent
    
    return "Unknown"
