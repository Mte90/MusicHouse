"""Folder organization analyzer for MusicHouse."""

import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from musichouse.log_setup import get_logger

if TYPE_CHECKING:
    from musichouse.leaderboard_cache import LeaderboardCache

logger = get_logger(__name__)


class FolderType(Enum):
    """Classification types for music folders."""
    GENRE_CONTAINER = "genre_container"      # has subfolders, no direct MP3s — already organized, skip
    CORRECT_ARTIST = "correct_artist"        # single artist, folder name matches artist
    MISNAMED_ARTIST = "misnamed_artist"      # single artist, folder name doesn't match
    MIXED = "mixed"                           # multiple artists in one folder
    EMPTY = "empty"                           # no files, no subfolders


class FolderInfo:
    """Info about a classified folder."""

    def __init__(self, path: Path, folder_type: FolderType, artists: list[str],
                 file_count: int, suggested_name: str | None = None):
        self.path = path
        self.folder_type = folder_type
        self.artists = artists
        self.file_count = file_count
        self.suggested_name = suggested_name

    def __repr__(self) -> str:
        return (f"FolderInfo(path={self.path}, type={self.folder_type.value}, "
                f"artists={self.artists}, files={self.file_count}, "
                f"suggested={self.suggested_name})")


def _normalize_name(name: str) -> str:
    """Normalize folder/artist name for comparison."""
    return " ".join(name.lower().strip().split())


def analyze_folder_structure(base_path: Path, cache: "LeaderboardCache") -> list[FolderInfo]:
    """
    Walk the folder tree under base_path. Classify each folder.

    Classification logic:
    - GENRE_CONTAINER: has subfolders, no direct MP3s (already organized)
    - CORRECT_ARTIST: single artist, folder name matches artist
    - MISNAMED_ARTIST: single artist, folder name doesn't match
    - MIXED: multiple artists in one folder
    - EMPTY: no files, no subfolders

    Args:
        base_path: Root directory to analyze.
        cache: LeaderboardCache with scanned file metadata.

    Returns:
        List of FolderInfo for all folders (genre containers and their subfolders).
    """
    results: list[FolderInfo] = []
    skipped_dirs: list[str] = []

    # Get all cached files with their paths and artists
    conn = cache._get_connection()
    cursor = conn.execute(
        "SELECT path, artist FROM scan_cache WHERE artist IS NOT NULL"
    )
    file_data = {row["path"]: row["artist"] for row in cursor.fetchall()}

    def _walk_dir(path: Path) -> list[Path]:
        """Recursively walk directories, catching OSError per entry."""
        dirs: list[Path] = []
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        entry_path = Path(entry.path)
                        if entry.is_dir(follow_symlinks=False):
                            dirs.append(entry_path)
                            dirs.extend(_walk_dir(entry_path))
                    except (PermissionError, OSError):
                        skipped_dirs.append(str(entry_path))
        except (PermissionError, OSError):
            skipped_dirs.append(str(path))
        return dirs

    all_dirs = _walk_dir(base_path)

    for dirpath in all_dirs:
        # Get subfolders with error handling
        subfolders: list[Path] = []
        try:
            with os.scandir(dirpath) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            subfolders.append(Path(entry.path))
                    except (PermissionError, OSError):
                        skipped_dirs.append(str(Path(entry.path)))
        except (PermissionError, OSError):
            skipped_dirs.append(str(dirpath))
            continue

        # Get files in this folder (direct children only, not recursive)
        files_in_folder: list[Path] = []
        try:
            with os.scandir(dirpath) as entries:
                for entry in entries:
                    try:
                        entry_path = Path(entry.path)
                        if entry.is_file() and entry_path.suffix.lower() == ".mp3":
                            files_in_folder.append(entry_path)
                    except (PermissionError, OSError):
                        skipped_dirs.append(str(entry_path))
        except (PermissionError, OSError):
            skipped_dirs.append(str(dirpath))
            continue

        # Get artists from cached data
        artists_in_folder: set[str] = set()
        for file_path in files_in_folder:
            file_str = str(file_path)
            if file_str in file_data:
                artist = file_data[file_str]
                if artist:
                    artists_in_folder.add(artist)

        has_subfolders = len(subfolders) > 0
        has_files = len(files_in_folder) > 0
        num_artists = len(artists_in_folder)

        # Classify the folder
        if has_subfolders and not has_files:
            # Genre container: has subfolders, no direct MP3s
            folder_type = FolderType.GENRE_CONTAINER
            results.append(FolderInfo(
                path=dirpath,
                folder_type=folder_type,
                artists=[],
                file_count=0
            ))
        elif not has_subfolders and not has_files:
            # Empty folder
            folder_type = FolderType.EMPTY
            results.append(FolderInfo(
                path=dirpath,
                folder_type=folder_type,
                artists=[],
                file_count=0
            ))
        elif not has_subfolders and num_artists == 1:
            # Single artist folder
            artist = next(iter(artists_in_folder))
            folder_name_normalized = _normalize_name(dirpath.name)
            artist_normalized = _normalize_name(artist)

            if folder_name_normalized == artist_normalized:
                folder_type = FolderType.CORRECT_ARTIST
                suggested_name = None
            else:
                folder_type = FolderType.MISNAMED_ARTIST
                suggested_name = artist

            results.append(FolderInfo(
                path=dirpath,
                folder_type=folder_type,
                artists=[artist],
                file_count=len(files_in_folder),
                suggested_name=suggested_name
            ))
        elif not has_subfolders and num_artists > 1:
            # Mixed artists
            folder_type = FolderType.MIXED
            results.append(FolderInfo(
                path=dirpath,
                folder_type=folder_type,
                artists=sorted(artists_in_folder),
                file_count=len(files_in_folder)
            ))
        elif has_subfolders and has_files:
            # Has both subfolders and files - treat as container
            folder_type = FolderType.GENRE_CONTAINER
            results.append(FolderInfo(
                path=dirpath,
                folder_type=folder_type,
                artists=sorted(artists_in_folder),
                file_count=len(files_in_folder)
            ))
        else:
            # Fallback: should not happen with the logic above
            folder_type = FolderType.EMPTY
            results.append(FolderInfo(
                path=dirpath,
                folder_type=folder_type,
                artists=[],
                file_count=0
            ))

    # Log summary warning for skipped directories
    if skipped_dirs:
        unique_skipped = list(dict.fromkeys(skipped_dirs))  # Preserve order, remove dups
        display_list = unique_skipped[:5]
        extra = len(unique_skipped) - 5
        if extra > 0:
            warning_msg = f"{', '.join(display_list)} (+{extra} more)"
        else:
            warning_msg = ', '.join(display_list)
        logger.warning(f"Skipped {len(unique_skipped)} unreadable directories: {warning_msg}")

    return results