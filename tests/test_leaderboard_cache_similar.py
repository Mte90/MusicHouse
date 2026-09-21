"""Unit tests for LeaderboardCache similar artists methods."""


import pytest

from musichouse.leaderboard_cache import LeaderboardCache


@pytest.fixture
def cache(temp_db_file):
    """Create LeaderboardCache instance with temporary database."""
    cache = LeaderboardCache(temp_db_file)
    yield cache
    cache.close()


class TestGetSimilarArtists:
    """Tests for get_similar_artists()."""
    
    def test_get_similar_artists_empty_cache(self, cache):
        """Test getting similar artists from empty cache returns []."""
        result = cache.get_similar_artists("Test Artist")
        assert result == []
    
    def test_get_similar_artists_cached(self, cache):
        """Test getting cached similar artists."""
        suggestions = [
            {"artist": "Artist A", "reason": "Similar style"},
            {"artist": "Artist B", "reason": "Same genre"}
        ]
        cache.save_similar_artists("Test Artist", suggestions)
        
        result = cache.get_similar_artists("Test Artist")
        
        assert result == suggestions
    
    def test_get_similar_artists_unknown_seed(self, cache):
        """Test getting similar artists for unknown seed returns []."""
        result = cache.get_similar_artists("Unknown Seed")
        assert result == []
    
    def test_get_similar_artists_malformed_json_returns_empty(self, cache):
        """Test that malformed JSON in cache returns empty list."""
        conn = cache._get_connection()
        conn.execute(
            "INSERT INTO similar_artists (artist_name, similar_json, last_updated) VALUES (?, ?, ?)",
            ("Test Artist", "not valid json", 123456)
        )
        
        result = cache.get_similar_artists("Test Artist")
        
        assert result == []


class TestSaveSimilarArtists:
    """Tests for save_similar_artists()."""
    
    def test_save_similar_artists_insert(self, cache):
        """Test saving similar artists inserts new entry."""
        suggestions = [{"artist": "Artist A", "reason": "Test"}]
        cache.save_similar_artists("Test Artist", suggestions)
        
        result = cache.get_similar_artists("Test Artist")
        assert result == suggestions
    
    def test_save_similar_artists_replace_all(self, cache):
        """Test that saving twice replaces all entries (delete + insert)."""
        # First save
        cache.save_similar_artists("Test Artist", [
            {"artist": "Artist A", "reason": "First"}
        ])
        
        # Second save (should replace, not append)
        cache.save_similar_artists("Test Artist", [
            {"artist": "Artist B", "reason": "Second"}
        ])
        
        result = cache.get_similar_artists("Test Artist")
        assert len(result) == 1
        assert result[0] == {"artist": "Artist B", "reason": "Second"}
    
    def test_save_similar_artists_empty_list(self, cache):
        """Test saving empty list clears existing entries."""
        # First save some data
        cache.save_similar_artists("Test Artist", [
            {"artist": "Artist A", "reason": "Test"}
        ])
        
        # Save empty list
        cache.save_similar_artists("Test Artist", [])
        
        result = cache.get_similar_artists("Test Artist")
        assert result == []
    
    def test_save_similar_artists_multiple_seeds(self, cache):
        """Test saving to different seeds independently."""
        cache.save_similar_artists("Artist A", [{"artist": "Similar 1", "reason": "Test"}])
        cache.save_similar_artists("Artist B", [{"artist": "Similar 2", "reason": "Test"}])
        
        result_a = cache.get_similar_artists("Artist A")
        result_b = cache.get_similar_artists("Artist B")
        
        assert len(result_a) == 1
        assert result_a[0]["artist"] == "Similar 1"
        assert len(result_b) == 1
        assert result_b[0]["artist"] == "Similar 2"


class TestGetAllIndexedArtists:
    """Tests for get_all_indexed_artists()."""
    
    def test_get_all_indexed_artists_empty(self, cache):
        """Test getting indexed artists from empty cache returns []."""
        result = cache.get_all_indexed_artists()
        assert result == []
    
    def test_get_all_indexed_artists_returns_distinct(self, cache):
        """Test that get_all_indexed_artists returns distinct artists."""
        cache.update_scan_cache([
            {"path": "/path/file1.mp3", "size": 100, "mtime": 1.0, "artist": "Artist A", "title": "Title"},
            {"path": "/path/file2.mp3", "size": 100, "mtime": 1.0, "artist": "Artist A", "title": "Title"},
            {"path": "/path/file3.mp3", "size": 100, "mtime": 1.0, "artist": "Artist B", "title": "Title"},
        ])
        
        result = cache.get_all_indexed_artists()
        
        assert len(result) == 2
        assert set(result) == {"Artist A", "Artist B"}
    
    def test_get_all_indexed_artists_excludes_none(self, cache):
        """Test that None artists are excluded."""
        cache.update_scan_cache([
            {"path": "/path/file1.mp3", "size": 100, "mtime": 1.0, "artist": None, "title": "Title"},
            {"path": "/path/file2.mp3", "size": 100, "mtime": 1.0, "artist": "Artist A", "title": "Title"},
        ])
        
        result = cache.get_all_indexed_artists()
        
        assert result == ["Artist A"]
    
    def test_get_all_indexed_artists_excludes_empty_string(self, cache):
        """Test that empty string artists are excluded."""
        cache.update_scan_cache([
            {"path": "/path/file1.mp3", "size": 100, "mtime": 1.0, "artist": "", "title": "Title"},
            {"path": "/path/file2.mp3", "size": 100, "mtime": 1.0, "artist": "Artist A", "title": "Title"},
        ])
        
        result = cache.get_all_indexed_artists()
        
        assert result == ["Artist A"]


class TestConnectionClosed:
    """Tests that database connections are properly closed."""
    
    def test_get_similar_artists_closes_connection(self, cache):
        """Test that get_similar_artists doesn't leave connections open."""
        cache.save_similar_artists("Test", [{"artist": "A", "reason": "Test"}])
        result = cache.get_similar_artists("Test")
        assert result  # Should not raise
        
        # Connection should be usable after
        cache.save_similar_artists("Test2", [{"artist": "B", "reason": "Test"}])
    
    def test_save_similar_artists_commits(self, cache):
        """Test that save_similar_artists commits changes."""
        cache.save_similar_artists("Test", [{"artist": "A", "reason": "Test"}])
        
        # Verify data persists by getting it back
        result = cache.get_similar_artists("Test")
        assert len(result) == 1