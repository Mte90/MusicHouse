"""Unit tests for AIClient with mocked API responses.

CRITICAL: These tests NEVER call real API endpoints.
All API calls are mocked using unittest.mock.patch.
"""

import json
import socket
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from musichouse.ai_client import AIClient


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def ai_client_no_key():
    """Create AIClient without API key (fallback mode)."""
    with patch('musichouse.ai_client.config.get_api_key', return_value=''), \
         patch('musichouse.ai_client.config.get_endpoint', return_value='http://localhost:8080'), \
         patch('musichouse.ai_client.config.get_model', return_value='test-model'):
        return AIClient()


@pytest.fixture
def ai_client_with_key():
    """Create AIClient with fake API key (for testing error handling)."""
    with patch('musichouse.ai_client.config.get_api_key', return_value='fake-key-for-testing'), \
         patch('musichouse.ai_client.config.get_endpoint', return_value='http://localhost:8080'), \
         patch('musichouse.ai_client.config.get_model', return_value='test-model'):
        return AIClient()


# ============================================================================
# Test: infer_tags() with valid filename
# ============================================================================
class TestInferTags:
    """Tests for AIClient.infer_tags() method."""

    def test_infer_tags_with_valid_filename(self, ai_client_no_key):
        """Test infer_tags returns fallback when no API key."""
        result = ai_client_no_key.infer_tags("Test Artist - Test Title.mp3")
        
        assert "artist" in result
        assert "title" in result
        assert result["artist"] == "Unknown"
        assert result["title"] == "Unknown"

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_infer_tags_with_api_success(self, mock_urlopen, ai_client_with_key):
        """Test infer_tags with successful API response."""
        # Mock API response
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"artist": "AI Detected Artist", "title": "AI Detected Title"}'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.infer_tags("Some File.mp3")

        assert result["artist"] == "AI Detected Artist"
        assert result["title"] == "AI Detected Title"
        mock_urlopen.assert_called_once()

    def test_infer_tags_with_api_failure(self, ai_client_with_key):
        """Test infer_tags falls back when API fails."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection error")

            result = ai_client_with_key.infer_tags("Some File.mp3")

            assert result["artist"] == "Unknown"
            assert result["title"] == "Unknown"


# ============================================================================
# Test: get_similar_artists()
# ============================================================================
class TestGetSimilarArtists:
    """Tests for AIClient.get_similar_artists() method."""

    def test_get_similar_artists_fallback(self, ai_client_no_key):
        """Test get_similar_artists returns fallback when no API key.
        
        Note: The fallback returns {"artists": ["Unknown Artist"]} but the method
        returns result.get("artists", []). Since fallback returns a dict with 
        "artists" key, this should work.
        """
        result = ai_client_no_key.get_similar_artists("Some Artist")

        # The fallback response is {"artists": ["Unknown Artist"]}
        # get_similar_artists returns result.get("artists", [])
        assert isinstance(result, list)
        assert result == ["Unknown Artist"]

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_with_api_success(self, mock_urlopen, ai_client_with_key):
        """Test get_similar_artists with successful API response.
        
        Note: _extract_result returns content directly. If content is a JSON array,
        the result is a list. get_similar_artists then calls result.get("artists", [])
        which fails on lists. This test exposes a bug in the implementation.
        """
        mock_response = MagicMock()
        # API returns a JSON array directly
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '["Artist A", "Artist B", "Artist C"]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.get_similar_artists("Some Artist")

        # Bug: _extract_result returns the list directly, then .get("artists", []) returns []
        # Expected behavior should be to return the list directly
        # This test documents the current (buggy) behavior
        assert result == ["Artist A", "Artist B", "Artist C"]
        mock_urlopen.assert_called_once()

    def test_get_similar_artists_with_api_failure(self, ai_client_with_key):
        """Test get_similar_artists falls back when API fails."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("API error")

            result = ai_client_with_key.get_similar_artists("Some Artist")

            assert result == ["Unknown Artist"]


# ============================================================================
# Test: get_artist_genres()
# ============================================================================
class TestGetArtistGenres:
    """Tests for AIClient.get_artist_genres() method."""

    def test_get_artist_genres_fallback(self, ai_client_no_key):
        """Test get_artist_genres returns fallback when no API key."""
        result = ai_client_no_key.get_artist_genres("Some Artist")

        assert isinstance(result, list)
        assert result == ["Unknown Genre"]

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_artist_genres_with_api_success(self, mock_urlopen, ai_client_with_key):
        """Test get_artist_genres with successful API response."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '["Rock", "Pop", "Alternative"]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.get_artist_genres("Some Artist")

        # Bug: same as get_similar_artists - returns [] instead of the list
        assert result == ["Rock", "Pop", "Alternative"]
        mock_urlopen.assert_called_once()

    def test_get_artist_genres_with_api_failure(self, ai_client_with_key):
        """Test get_artist_genres falls back when API fails."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("API error")

            result = ai_client_with_key.get_artist_genres("Some Artist")

            assert result == ["Unknown Genre"]


# ============================================================================
# Test: Fallback when API key not configured
# ============================================================================
class TestFallbackNoApiKey:
    """Tests for fallback behavior when no API key is configured."""

    def test_infer_tags_no_api_key(self, ai_client_no_key):
        """Test infer_tags fallback without API key."""
        result = ai_client_no_key.infer_tags("filename.mp3")
        assert result == {"artist": "Unknown", "title": "Unknown"}

    def test_get_similar_artists_no_api_key(self, ai_client_no_key):
        """Test get_similar_artists fallback without API key."""
        result = ai_client_no_key.get_similar_artists("Artist Name")
        assert result == ["Unknown Artist"]

    def test_get_artist_genres_no_api_key(self, ai_client_no_key):
        """Test get_artist_genres fallback without API key."""
        result = ai_client_no_key.get_artist_genres("Artist Name")
        assert result == ["Unknown Genre"]


# ============================================================================
# Test: Fallback when API fails
# ============================================================================
class TestFallbackApiFailure:
    """Tests for fallback behavior when API call fails."""

    def test_infer_tags_api_error(self, ai_client_with_key):
        """Test infer_tags fallback on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection timeout")
            
            result = ai_client_with_key.infer_tags("file.mp3")
            assert result == {"artist": "Unknown", "title": "Unknown"}

    def test_get_similar_artists_api_error(self, ai_client_with_key):
        """Test get_similar_artists fallback on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection timeout")
            
            result = ai_client_with_key.get_similar_artists("Artist")
            assert result == ["Unknown Artist"]

    def test_get_artist_genres_api_error(self, ai_client_with_key):
        """Test get_artist_genres fallback on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection timeout")
            
            result = ai_client_with_key.get_artist_genres("Artist")
            assert result == ["Unknown Genre"]

    def test_api_connection_refused(self, ai_client_with_key):
        """Test fallback on connection refused."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = ConnectionRefusedError("Connection refused")
            
            result = ai_client_with_key.infer_tags("file.mp3")
            assert result == {"artist": "Unknown", "title": "Unknown"}


# ============================================================================
# Test: JSON parsing from response
# ============================================================================
class TestJsonParsing:
    """Tests for JSON parsing from API responses."""

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_parse_valid_json_response(self, mock_urlopen, ai_client_with_key):
        """Test parsing valid JSON from API response."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"artist": "Parsed Artist", "title": "Parsed Title"}'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.infer_tags("file.mp3")

        assert result["artist"] == "Parsed Artist"
        assert result["title"] == "Parsed Title"

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_parse_json_with_extra_text(self, mock_urlopen, ai_client_with_key):
        """Test parsing JSON when response has extra text around it."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": 'Here is the result: {"artist": "Extracted Artist", "title": "Extracted Title"} and some more text'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.infer_tags("file.mp3")

        assert result["artist"] == "Extracted Artist"
        assert result["title"] == "Extracted Title"

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_parse_invalid_json_returns_error(self, mock_urlopen, ai_client_with_key):
        """Test that invalid JSON returns error dict."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": 'This is not valid JSON'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.infer_tags("file.mp3")

        assert "error" in result


# ============================================================================
# Test: Timeout handling
# ============================================================================
class TestTimeoutHandling:
    """Tests for timeout handling in API calls."""

    def test_timeout_error(self, ai_client_with_key):
        """Test fallback on timeout error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Request timed out")
            
            result = ai_client_with_key.infer_tags("file.mp3")
            assert result == {"artist": "Unknown", "title": "Unknown"}

    def test_socket_timeout(self, ai_client_with_key):
        """Test fallback on socket timeout."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = socket.timeout("Socket timeout")
            
            result = ai_client_with_key.get_similar_artists("Artist")
            assert result == ["Unknown Artist"]


# ============================================================================
# Test: Ensure no real API calls are made
# ============================================================================
class TestNoRealApiCalls:
    """Tests to ensure no real API calls are made."""

    def test_no_real_api_call_with_mock(self, ai_client_with_key):
        """Verify that urlopen is properly mocked and not called."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            # Don't call any method - just verify mock is set up
            assert mock_urlopen.call_count == 0

            # Now make a call
            ai_client_with_key.infer_tags("file.mp3")
            
            # Verify mock WAS called (proving we used the mock, not real API)
            assert mock_urlopen.call_count == 1

    def test_api_key_not_sent_when_none(self, ai_client_no_key):
        """Verify API key is None and fallback is used."""
        assert ai_client_no_key.api_key == ""

        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            result = ai_client_no_key.infer_tags("file.mp3")
            
            # urlopen should NOT be called when no API key
            mock_urlopen.assert_not_called()
            
            # Should get fallback response
            assert result == {"artist": "Unknown", "title": "Unknown"}




# ============================================================================
# Test: Response parsing error handling
# ============================================================================
class TestResponseParseError:

    """Tests for response parsing errors."""



    def test_response_parse_error(self, ai_client_with_key):

        """Test that response parsing errors are handled gracefully."""

        # Mock response that will cause JSON parse error in _extract_result

        mock_response_data = {

            "choices": [{

                "message": {

                    "content": "Invalid response without JSON"  # No valid JSON

                }

            }]

        }

        

        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:

            mock_response = MagicMock()

            mock_response.read.return_value = json.dumps(mock_response_data).encode('utf-8')

            mock_urlopen.return_value.__enter__.return_value = mock_response

            

            # Should handle parse error and return error dict

            result = ai_client_with_key.infer_tags("file.mp3")

            assert "error" in result



    def test_extract_result_exception_path(self, ai_client_with_key):

        """Test _extract_result handles exceptions and logs error."""

        # Mock response that causes exception during extraction

        mock_response_data = {

            "choices": []  # Empty choices will cause IndexError

        }

        

        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:

            mock_response = MagicMock()

            mock_response.read.return_value = json.dumps(mock_response_data).encode('utf-8')

            mock_urlopen.return_value.__enter__.return_value = mock_response

            

            # Should handle exception and return error dict

            result = ai_client_with_key.infer_tags("file.mp3")

            assert "error" in result
            assert "error" in result
