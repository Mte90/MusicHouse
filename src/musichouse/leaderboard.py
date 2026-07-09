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

    def update_from_files(self, files: List[Path]) -> List[Tuple[str, int]]:
        """Update leaderboard from a list of MP3 files.
        
        Uses cached tag data from scan_cache to avoid redundant eyed3.load() calls.
        """
        artists = []
        cache = leaderboard_cache.LeaderboardCache(self.cache_path)

        try:
            for file_path in files:
                path_str = str(file_path)
                artist = None
                
                # Try to get cached tag data first - avoids reloading the file
                cached_info = cache.get_cached_info(path_str)
                if cached_info and cached_info.get('tag_data'):
                    artist = cached_info['tag_data'].get('artist')
                elif cached_info and cached_info.get('artist'):
                    # Fallback to cached artist field if tag_data not available
                    artist = cached_info['artist']
                
                # Only load file if no cached data available
                if not artist:
                    try:
                        audiofile = load_mp3_safely(file_path)
                        if audiofile and audiofile.tag:
                            artist = audiofile.tag.artist or ""
                    except Exception as e:
                        logger.error(f"Error scanning {file_path}: {e}")
                
                if artist:
                    artists.append(artist)

            counter = Counter(artists)
            self._top_artists = counter.most_common(10)

            # Update SQLite cache with artist counts
            cache.update_artists(dict(counter.most_common()))
        finally:
            cache.close()
        
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
        
        # Update SQLite cache with fresh connection
        cache = leaderboard_cache.LeaderboardCache(self.cache_path)
        cache.update_artists(artist_counts)
        cache.close()
        
        return self._top_artists

    def get_top_artists(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get the top N artists."""
        return self._top_artists[:limit]

    def reset(self) -> None:
        """Reset the leaderboard and clear cache."""
        # Clear cache with fresh connection
        cache = leaderboard_cache.LeaderboardCache(self.cache_path)
        cache.clear()
        cache.close()

    def __del__(self):
        """Cleanup database connection."""
        if hasattr(self, '_cache') and self._cache:
            self._cache.close()
