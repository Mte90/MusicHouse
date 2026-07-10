"""Filename and folder parsing utilities for MusicHouse."""

import re
from pathlib import Path
from typing import Optional


def parse_filename(filename: str, file_path: Optional[Path] = None) -> tuple[str, str]:
    """Parse MP3 filename to extract artist and title.
    
    Handles patterns:
    - "artist - title.mp3" with flexible spacing around hyphen/en-dash/em-dash
    - "01. Artist - Title.mp3" → strip leading track number + dot
    - "01 - Artist - Title.mp3" → strip leading track number
    - "Artist - 01 - Title.mp3" → strip middle track number
    - "01 Track.mp3" → no artist, title="Track"
    - "Artist_Title.mp3" → underscore separator
    - "Artist — Title.mp3" → em-dash separator
    
    If no hyphen found, uses parent directory name as artist.
    
    Args:
        filename: The filename string (with .mp3 extension).
        file_path: Optional full path to the file (used to get folder name).
        
    Returns:
        Tuple of (artist, title) extracted from filename.
    """
    # If no .mp3 extension, return the full name for both
    if not filename.lower().endswith('.mp3'):
        return (filename.strip(), filename.strip())
    
    # Strip .mp3 extension first for processing
    name_without_ext = filename[:-4]
    
    # Strip leading track number patterns: "01. " or "01 - " or "01 "
    # Pattern: digits followed by separator (dot/hyphen/em-dash) and optional space
    stripped_name = name_without_ext
    leading_track_match = re.match(r'^(\d+)\s*[.\-—]\s+(.+)$', name_without_ext)
    if leading_track_match:
        stripped_name = leading_track_match.group(2)
    
    # Pattern: "artist - title" with flexible spacing around hyphen/en-dash/em-dash/underscore
    # Using re.UNICODE for proper unicode character handling
    match = re.match(r'^(.+?)\s*[-–—_]\s+(.+)$', stripped_name, re.IGNORECASE | re.UNICODE)
    if match:
        artist = match.group(1).strip()
        title = match.group(2).strip()
        # Strip middle track number pattern: "Artist - 01 - Title" → "Artist - Title"
        middle_track_match = re.match(r'^(.+?)\s*[-–—]\s+\d+\s*[-–—]\s+(.+)$', artist + ' - ' + title, re.UNICODE)
        if middle_track_match:
            artist = middle_track_match.group(1).strip()
            title = middle_track_match.group(2).strip()
        return (artist, title)
    
    # Fallback: split on first hyphen/dash/underscore
    separators = ['-', '–', '—', '_']
    for sep in separators:
        if sep in stripped_name:
            idx = stripped_name.index(sep)
            artist = stripped_name[:idx].strip()
            title = stripped_name[idx+1:].strip()
            return (artist, title)
    
    # Check for track number prefix like "01 Track.mp3" (no hyphen)
    no_artist_match = re.match(r'^(\d+)\s+(.+)$', stripped_name)
    if no_artist_match:
        title = no_artist_match.group(2).strip()
        if title:
            # Use folder artist if available, otherwise return empty artist
            if file_path:
                folder_artist = get_artist_from_folder(file_path)
                if folder_artist and folder_artist != "Unknown":
                    return (folder_artist, title)
            return ("", title)
    
    # No hyphen found - use parent directory name as artist
    name = stripped_name
    
    if not name:
        return ("", "")
    
    # If we have the full path, use folder name as artist
    if file_path:
        folder_artist = get_artist_from_folder(file_path)
        if folder_artist and folder_artist != "Unknown":
            # If the name part is a number, use folder name as artist
            # This handles cases like "123.mp3" where 123 would be wrong artist
            if name.strip().isdigit():
                return (folder_artist, name)
            return (folder_artist, name)
    # Fallback: return name as both artist and title
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
    
    # Must have a hyphen/dash/underscore in the filename
    if not any(sep in filename for sep in ['-', '–', '—', '_']):
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
