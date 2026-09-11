"""HTTP client for MusicBrainz artist genre lookup with SQLite caching and rate limiting."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from musichouse.error_handling import MusicHouseError
from musichouse.leaderboard_cache import LeaderboardCache


class MusicBrainzError(MusicHouseError):
    """Base exception for MusicBrainz API errors."""


class MusicBrainzNotFoundError(MusicBrainzError):
    """Artist not found on MusicBrainz."""


class MusicBrainzClient:
    """HTTP client for MusicBrainz artist genre lookup, with SQLite caching and rate limiting."""

    USER_AGENT = "MusicHouse/1.0.0 (https://github.com/user/musichouse)"
    BASE_URL = "https://musicbrainz.org/ws/2"
    RATE_LIMIT_SECONDS = 1.0

    def __init__(self, cache: LeaderboardCache):
        """Initialize MusicBrainz client.

        Args:
            cache: LeaderboardCache instance for SQLite caching.
        """
        self._cache = cache
        self._last_request_time: float = 0.0

    def get_artist_genres(self, artist_name: str) -> list[str]:
        """Return genre names for an artist.

        Checks SQLite cache first. If not cached: searches MusicBrainz for MBID,
        fetches genres, caches result, returns genres. If artist not found on
        MusicBrainz: returns empty list and caches empty list. Rate-limited to
        maintain 1 req/sec between API calls.

        Args:
            artist_name: Name of the artist to look up.

        Returns:
            List of genre name strings. Empty list if artist not found.
        """
        cached = self._cache.get_artist_genres(artist_name)
        if cached is not None:
            return cached

        mbid = self._search_artist(artist_name)
        if mbid is None:
            self._cache.set_artist_genres(artist_name, [])
            return []

        genres = self._fetch_genres(mbid)
        self._cache.set_artist_genres(artist_name, genres)
        return genres

    def _search_artist(self, name: str) -> str | None:
        """Search MusicBrainz for an artist.

        Args:
            name: Artist name to search for.

        Returns:
            MBID of top result or None if not found.
        """
        encoded_name = urllib.parse.quote(name)
        url = f"{self.BASE_URL}/artist?query=artist:\"{encoded_name}\"&fmt=json"

        response = self._make_request(url)

        if response.get("count", 0) == 0:
            return None

        artists = response.get("artists", [])
        if not artists:
            return None

        return artists[0].get("id")

    def _fetch_genres(self, mbid: str) -> list[str]:
        """Fetch genres for an artist by MBID.

        Args:
            mbid: MusicBrainz ID of the artist.

        Returns:
            List of genre name strings.
        """
        url = f"{self.BASE_URL}/artist/{mbid}?inc=genres&fmt=json"

        response = self._make_request(url)
        genres_data = response.get("genres", [])
        return [g["name"] for g in genres_data if "name" in g]

    def _make_request(self, url: str) -> dict:
        """Make HTTP GET request with rate limiting and error handling.

        Enforces rate limit by sleeping if needed. Handles 503/429 by reading
        Retry-After header, sleeping with jitter, and retrying once.

        Args:
            url: Full URL to request.

        Returns:
            Parsed JSON response as dict.

        Raises:
            MusicBrainzNotFoundError: If artist not found (404).
            MusicBrainzError: For other HTTP errors or network failures.
        """
        self._enforce_rate_limit()

        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.USER_AGENT},
            method="GET"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                self._last_request_time = time.time()
                data = response.read().decode("utf-8")
                return json.loads(data)

        except urllib.error.HTTPError as e:
            self._last_request_time = time.time()

            try:
                if e.code == 404:
                    raise MusicBrainzNotFoundError(f"Artist not found: {url}")

                if e.code in (503, 429):
                    retry_after = self._get_retry_after(e)
                    time.sleep(retry_after + 0.5)

                    try:
                        with urllib.request.urlopen(req, timeout=15) as retry_response:
                            self._last_request_time = time.time()
                            data = retry_response.read().decode("utf-8")
                            return json.loads(data)
                    except urllib.error.HTTPError as retry_error:
                        try:
                            raise MusicBrainzError(f"HTTP error {retry_error.code}: {retry_error.reason}")
                        finally:
                            retry_error.close()

                raise MusicBrainzError(f"HTTP error {e.code}: {e.reason}")
            finally:
                e.close()

        except urllib.error.URLError as e:
            raise MusicBrainzError(f"Network error: {e.reason}")

        except TimeoutError:
            raise MusicBrainzError("Request timed out after 15s")

        except json.JSONDecodeError as e:
            raise MusicBrainzError(f"Failed to parse JSON response: {e}")

    def _enforce_rate_limit(self) -> None:
        """Sleep to maintain rate limit between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            sleep_time = self.RATE_LIMIT_SECONDS - elapsed
            time.sleep(sleep_time)

    def _get_retry_after(self, error: urllib.error.HTTPError) -> float:
        """Extract retry delay from Retry-After header.

        Args:
            error: HTTPError with Retry-After header.

        Returns:
            Seconds to wait before retry.
        """
        retry_header = error.headers.get("Retry-After")
        if retry_header:
            try:
                return float(retry_header)
            except (ValueError, TypeError):
                pass
        return 1.0