"""Leaderboard module for MusicHouse."""

from typing import Optional, List, Tuple
from collections import Counter
from pathlib import Path

from musichouse import logging
from musichouse import leaderboard_cache
from musichouse.utils import load_mp3_safely

logger = logging.get_logger(__name__)


class Leaderboard:
    """Manages the artist leaderboard from scanned music files."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the leaderboard."""
        if cache_dir is None:
            from musichouse import config
            cache_dir = config.get_config_dir()
        
        self.cache_path = cache_dir / "leaderboard.db"
        self._cache = leaderboard_cache.LeaderboardCache(self.cache_path)
        
        # Load existing artists from DB
        self._top_artists = self._cache.get_all_artists()
        self._cache.close()  # IMPORTANT: close after loading

    def update_from_files(self, files: List[Path]) -> List[Tuple[str, int]]:
        """Update leaderboard from a list of MP3 files."""
        artists = []

        for file_path in files:
            try:
                audiofile = load_mp3_safely(file_path)
                if audiofile and audiofile.tag:
                    artist = audiofile.tag.artist or ""
                    if artist:
                        artists.append(artist)
            except Exception as e:
                logger.error(f"Error scanning {file_path}: {e}")

        counter = Counter(artists)
        self._top_artists = counter.most_common(10)

        # Update SQLite cache
        self._cache.update_artists(dict(counter.most_common()))
        self._cache.close()  # IMPORTANT: close after update
        
        return self._top_artists
    
    def update_from_artist_counts(
        self, 
        artist_counts: dict
    ) -> List[Tuple[str, int]]:
        """Update leaderboard from pre-computed artist counts dict."""
        # logger.info(f"Updating leaderboard with {len(artist_counts)} artists")  # Too verbose during scan
        
        # Sort by count descending
        self._top_artists = sorted(
            artist_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Update SQLite cache
        self._cache.update_artists(artist_counts)
        self._cache.close()  # IMPORTANT: close after update
        
        return self._top_artists

    def get_top_artists(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get the top N artists."""
        return self._top_artists[:limit]

    def reset(self) -> None:
        """Reset the leaderboard and clear cache."""
        if self._cache:
            self._cache.clear()
            self._cache.close()

    def __del__(self):
        """Cleanup database connection."""
        if hasattr(self, '_cache') and self._cache:
            self._cache.close()
