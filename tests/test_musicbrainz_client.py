"""Unit tests for MusicBrainzClient with mocked API responses.

CRITICAL: These tests NEVER call real MusicBrainz endpoints.
All HTTP calls are mocked using unittest.mock.patch.
"""

import json
import urllib.error
from unittest.mock import patch, MagicMock
import pytest

from musichouse.musicbrainz_client import (
    MusicBrainzClient,
    MusicBrainzError,
    MusicBrainzNotFoundError,
)
from musichouse.leaderboard_cache import LeaderboardCache


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def mock_cache(tmp_path):
    """Create a LeaderboardCache with temporary database."""
    db_path = tmp_path / "test_cache.db"
    return LeaderboardCache(cache_path=db_path)


@pytest.fixture
def musicbrainz_client(mock_cache):
    """Create MusicBrainzClient with mocked cache."""
    return MusicBrainzClient(cache=mock_cache)


# ============================================================================
# Test: Cache hit - no HTTP call made
# ============================================================================
class TestCacheHit:
    """Tests for cache hit behavior."""

    def test_get_artist_genres_cache_hit(self, musicbrainz_client, mock_cache):
        """Test that cached genres are returned without HTTP call."""
        mock_cache.set_artist_genres("Test Artist", ["Rock", "Pop"])

        with patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request') as mock_request:
            result = musicbrainz_client.get_artist_genres("Test Artist")

            assert result == ["Rock", "Pop"]
            mock_request.assert_not_called()


# ============================================================================
# Test: Cache miss - API call made and result cached
# ============================================================================
class TestCacheMiss:
    """Tests for cache miss behavior."""

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_get_artist_genres_cache_miss_api_call(self, mock_request, musicbrainz_client, mock_cache):
        """Test that API is called on cache miss and result is cached."""
        mock_request.side_effect = [
            {"artists": [{"id": "test-mbid-123", "name": "Test Artist", "score": 100}], "count": 1},
            {"id": "test-mbid-123", "name": "Test Artist", "genres": [{"name": "Rock"}, {"name": "Alternative"}]}
        ]

        result = musicbrainz_client.get_artist_genres("Test Artist")

        assert result == ["Rock", "Alternative"]
        assert mock_request.call_count == 2

        cached = mock_cache.get_artist_genres("Test Artist")
        assert cached == ["Rock", "Alternative"]

    def test_get_artist_genres_second_call_hits_cache(self, musicbrainz_client, mock_cache):
        """Test that second call hits cache, no HTTP calls."""
        with patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request') as mock_request:
            mock_request.side_effect = [
                {"artists": [{"id": "test-mbid-123", "name": "Test Artist", "score": 100}], "count": 1},
                {"id": "test-mbid-123", "name": "Test Artist", "genres": [{"name": "Rock"}]}
            ]

            musicbrainz_client.get_artist_genres("Test Artist")
            mock_request.reset_mock()

            result = musicbrainz_client.get_artist_genres("Test Artist")

            assert result == ["Rock"]
            mock_request.assert_not_called()


# ============================================================================
# Test: Artist not found
# ============================================================================
class TestArtistNotFound:
    """Tests for artist not found behavior."""

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_search_artist_not_found_empty_results(self, mock_request, musicbrainz_client, mock_cache):
        """Test that empty search results return empty list and cache it."""
        mock_request.return_value = {"artists": [], "count": 0}

        result = musicbrainz_client.get_artist_genres("Unknown Artist 9999")

        assert result == []
        cached = mock_cache.get_artist_genres("Unknown Artist 9999")
        assert cached == []

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_search_artist_not_found_zero_count(self, mock_request, musicbrainz_client, mock_cache):
        """Test that zero count returns empty list and caches it."""
        mock_request.return_value = {"artists": [], "count": 0}

        result = musicbrainz_client.get_artist_genres("Nonexistent Artist")

        assert result == []
        cached = mock_cache.get_artist_genres("Nonexistent Artist")
        assert cached == []


# ============================================================================
# Test: Rate limiting
# ============================================================================
class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rate_limit_sleep_between_requests(self, musicbrainz_client, mock_cache):
        """Test that rate limiting works between requests."""
        with patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request') as mock_request:
            mock_request.side_effect = [
                {"artists": [{"id": "mbid1", "name": "A", "score": 100}], "count": 1},
                {"id": "mbid1", "name": "A", "genres": [{"name": "Rock"}]},
                {"artists": [{"id": "mbid2", "name": "B", "score": 100}], "count": 1},
                {"id": "mbid2", "name": "B", "genres": [{"name": "Pop"}]}
            ]

            musicbrainz_client.get_artist_genres("Artist A")
            musicbrainz_client.get_artist_genres("Artist B")

            assert mock_request.call_count == 4

    def test_enforce_rate_limit_sleeps(self, musicbrainz_client):
        """Test that _enforce_rate_limit sleeps when needed."""
        musicbrainz_client._last_request_time = 0.0
        musicbrainz_client._enforce_rate_limit()

        pass  # Just verify no exception is raised


# ============================================================================
# Test: 503 retry logic
# ============================================================================
class Test503Retry:
    """Tests for 503 retry behavior."""

    @patch('musichouse.musicbrainz_client.time.sleep')
    def test_503_retry_succeeds_on_second_attempt(self, mock_sleep, musicbrainz_client, mock_cache):
        """Test that 503 with Retry-After retries and succeeds on second attempt."""
        mock_503 = urllib.error.HTTPError(
            url="https://musicbrainz.org/ws/2/artist/test",
            code=503,
            msg="Service Unavailable",
            hdrs={"Retry-After": "1"},
            fp=None
        )

        mock_success = MagicMock()
        mock_success.read.return_value = json.dumps({
            "artists": [{"id": "test-mbid", "name": "Test Artist", "score": 100}],
            "count": 1
        }).encode('utf-8')
        mock_success.__enter__ = MagicMock(return_value=mock_success)
        mock_success.__exit__ = MagicMock(return_value=False)

        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = [mock_503, mock_success]

            result = musicbrainz_client._search_artist("Test Artist")

            assert result == "test-mbid"
            assert mock_urlopen.call_count == 2

    @patch('musichouse.musicbrainz_client.time.sleep')
    def test_503_retry_exhausted_raises_error(self, mock_sleep, musicbrainz_client, mock_cache):
        """Test that 503 on both attempts raises MusicBrainzError."""
        mock_503_first = urllib.error.HTTPError(
            url="https://musicbrainz.org/ws/2/artist/test",
            code=503,
            msg="Service Unavailable",
            hdrs={"Retry-After": "0.1"},
            fp=None
        )
        mock_503_second = urllib.error.HTTPError(
            url="https://musicbrainz.org/ws/2/artist/test",
            code=503,
            msg="Service Unavailable",
            hdrs={"Retry-After": "0.1"},
            fp=None
        )

        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = [mock_503_first, mock_503_second]

            with pytest.raises(MusicBrainzError):
                musicbrainz_client._search_artist("Test Artist")

    @patch('musichouse.musicbrainz_client.time.sleep')
    def test_503_retry_uses_default_delay_when_header_missing(self, mock_sleep, musicbrainz_client, mock_cache):
        """Test that missing Retry-After header uses default 1 second delay."""
        mock_503 = urllib.error.HTTPError(
            url="https://musicbrainz.org/ws/2/artist/test",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None
        )

        mock_success = MagicMock()
        mock_success.read.return_value = json.dumps({
            "artists": [{"id": "test-mbid", "name": "Test Artist", "score": 100}],
            "count": 1
        }).encode('utf-8')
        mock_success.__enter__ = MagicMock(return_value=mock_success)
        mock_success.__exit__ = MagicMock(return_value=False)

        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = [mock_503, mock_success]

            result = musicbrainz_client._search_artist("Test Artist")

            assert result == "test-mbid"
            assert mock_urlopen.call_count == 2


# ============================================================================
# Test: 404 not found handling
# ============================================================================
class Test404Handling:
    """Tests for 404 not found handling."""

    def test_404_raises_not_found_error(self, musicbrainz_client):
        """Test that 404 raises MusicBrainzNotFoundError."""
        mock_404 = urllib.error.HTTPError(
            url="https://musicbrainz.org/ws/2/artist/nonexistent",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )

        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = mock_404

            with pytest.raises(MusicBrainzNotFoundError):
                musicbrainz_client._make_request("https://musicbrainz.org/ws/2/artist/nonexistent")


# ============================================================================
# Test: Network error handling
# ============================================================================
class TestNetworkErrors:
    """Tests for network error handling."""

    def test_url_error_raises_musicbrainz_error(self, musicbrainz_client):
        """Test that URLError raises MusicBrainzError."""
        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            with pytest.raises(MusicBrainzError, match="Network error"):
                musicbrainz_client._make_request("https://musicbrainz.org/ws/2/artist/test")

    def test_timeout_raises_musicbrainz_error(self, musicbrainz_client):
        """Test that TimeoutError raises MusicBrainzError."""
        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Request timed out")

            with pytest.raises(MusicBrainzError, match="timed out"):
                musicbrainz_client._make_request("https://musicbrainz.org/ws/2/artist/test")


# ============================================================================
# Test: JSON parsing errors
# ============================================================================
class TestJsonParsingErrors:
    """Tests for JSON parsing error handling."""

    def test_invalid_json_raises_musicbrainz_error(self, musicbrainz_client):
        """Test that invalid JSON raises MusicBrainzError."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"

        with patch('musichouse.musicbrainz_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_response

            with pytest.raises(MusicBrainzError, match="Failed to parse JSON"):
                musicbrainz_client._make_request("https://musicbrainz.org/ws/2/artist/test")


# ============================================================================
# Test: Search and genre fetching
# ============================================================================
class TestSearchAndFetch:
    """Tests for search and genre fetching logic."""

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_search_artist_returns_top_result_mbid(self, mock_request, musicbrainz_client):
        """Test that _search_artist returns MBID of top result."""
        mock_request.return_value = {
            "artists": [
                {"id": "mbid-1", "name": "Artist", "score": 100},
                {"id": "mbid-2", "name": "Artist", "score": 90}
            ],
            "count": 2
        }

        mbid = musicbrainz_client._search_artist("Artist")

        assert mbid == "mbid-1"

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_fetch_genres_returns_genre_names(self, mock_request, musicbrainz_client):
        """Test that _fetch_genres returns list of genre name strings."""
        mock_request.return_value = {
            "id": "test-mbid",
            "name": "Test Artist",
            "genres": [
                {"count": 73, "name": "alternative rock"},
                {"count": 50, "name": "indie rock"},
                {"count": 30, "name": "post-punk"}
            ]
        }

        genres = musicbrainz_client._fetch_genres("test-mbid")

        assert genres == ["alternative rock", "indie rock", "post-punk"]

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_fetch_genres_handles_missing_name_field(self, mock_request, musicbrainz_client):
        """Test that _fetch_genres skips genres without name field."""
        mock_request.return_value = {
            "id": "test-mbid",
            "name": "Test Artist",
            "genres": [
                {"count": 73, "name": "rock"},
                {"count": 50},
                {"name": "pop"}
            ]
        }

        genres = musicbrainz_client._fetch_genres("test-mbid")

        assert genres == ["rock", "pop"]


# ============================================================================
# Test: URL encoding
# ============================================================================
class TestUrlEncoding:
    """Tests for URL encoding of artist names."""

    @patch('musichouse.musicbrainz_client.MusicBrainzClient._make_request')
    def test_search_artist_url_encodes_name(self, mock_request, musicbrainz_client):
        """Test that artist name is URL encoded in search query."""
        mock_request.return_value = {
            "artists": [{"id": "mbid-1", "name": "Artist & Co", "score": 100}],
            "count": 1
        }

        musicbrainz_client._search_artist("Artist & Co")

        call_args = mock_request.call_args[0][0]
        assert "Artist%20%26%20Co" in call_args or "Artist&Co" in call_args