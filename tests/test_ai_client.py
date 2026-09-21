"""Unit tests for AIClient with mocked API responses.

CRITICAL: These tests NEVER call real API endpoints.
All API calls are mocked using unittest.mock.patch.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from musichouse.ai_client import AIClient
from musichouse.error_handling import APIConnectionError, APIParseError, APITimeoutError


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
        """Test infer_tags raises APIConnectionError when API fails."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection error")

            with pytest.raises(APIConnectionError):
                ai_client_with_key.infer_tags("Some File.mp3")


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
        """Test get_similar_artists raises APIConnectionError when API fails."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("API error")

            with pytest.raises(APIConnectionError):
                ai_client_with_key.get_similar_artists("Some Artist")


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
        """Test get_artist_genres raises APIConnectionError when API fails."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("API error")

            with pytest.raises(APIConnectionError):
                ai_client_with_key.get_artist_genres("Some Artist")


# ============================================================================
# Test: Error handling paths
# ============================================================================
class TestErrorHandling:
    """Tests for error handling in AIClient."""

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_http_error(self, mock_urlopen, ai_client_with_key):
        """Test HTTP error handling (401, 403, 500, etc.)."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'http://localhost:8080', 401, 'Unauthorized', {}, None
        )

        with pytest.raises(APIConnectionError):
            ai_client_with_key.get_similar_artists("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_timeout_error(self, mock_urlopen, ai_client_with_key):
        """Test timeout error handling."""
        mock_urlopen.side_effect = TimeoutError("Request timed out")

        with pytest.raises(APITimeoutError):
            ai_client_with_key.get_similar_artists("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_url_error(self, mock_urlopen, ai_client_with_key):
        """Test URL error handling (connection refused, DNS failure)."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with pytest.raises(APIConnectionError):
            ai_client_with_key.get_similar_artists("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_connection_refused(self, mock_urlopen, ai_client_with_key):
        """Test connection refused error handling."""
        mock_urlopen.side_effect = ConnectionRefusedError("Connection refused")

        with pytest.raises(APIConnectionError):
            ai_client_with_key.get_similar_artists("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_connection_error(self, mock_urlopen, ai_client_with_key):
        """Test connection error handling."""
        mock_urlopen.side_effect = ConnectionError("Network error")

        with pytest.raises(APIConnectionError):
            ai_client_with_key.get_similar_artists("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_os_error(self, mock_urlopen, ai_client_with_key):
        """Test OS error handling."""
        mock_urlopen.side_effect = OSError("Network unreachable")

        with pytest.raises(APIConnectionError):
            ai_client_with_key.get_similar_artists("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_call_api_invalid_json(self, mock_urlopen, ai_client_with_key):
        """Test invalid JSON error handling."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'not valid json'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(APIParseError):
            ai_client_with_key.get_similar_artists("Artist")


# ============================================================================
# Test: Validation errors in get_similar_artists_json
# ============================================================================
class TestSimilarArtistsJsonValidation:
    """Tests for validation errors in get_similar_artists_json."""

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_response_not_list(self, mock_urlopen, ai_client_with_key):
        """Test validation when API returns non-list response."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"not": "a list"}'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(TypeError):
            ai_client_with_key.get_similar_artists_json("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_item_not_dict(self, mock_urlopen, ai_client_with_key):
        """Test validation when list item is not a dict."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '["Artist A", "Artist B"]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(TypeError):
            ai_client_with_key.get_similar_artists_json("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_missing_artist_field(self, mock_urlopen, ai_client_with_key):
        """Test validation when item missing artist field."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"reason": "No artist name"}]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(ValueError):
            ai_client_with_key.get_similar_artists_json("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_empty_artist_name(self, mock_urlopen, ai_client_with_key):
        """Test validation when artist name is empty."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"artist": "", "reason": "Empty name"}]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(ValueError):
            ai_client_with_key.get_similar_artists_json("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_reason_not_string(self, mock_urlopen, ai_client_with_key):
        """Test validation when reason is not a string."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"artist": "Artist A", "reason": 123}]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(TypeError):
            ai_client_with_key.get_similar_artists_json("Artist")


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
    """Tests for typed exceptions when API call fails."""

    def test_infer_tags_api_error(self, ai_client_with_key):
        """Test infer_tags raises APIConnectionError on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection timeout")
            
            with pytest.raises(APIConnectionError):
                ai_client_with_key.infer_tags("file.mp3")

    def test_get_similar_artists_api_error(self, ai_client_with_key):
        """Test get_similar_artists raises APIConnectionError on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection timeout")
            
            with pytest.raises(APIConnectionError):
                ai_client_with_key.get_similar_artists("Artist")

    def test_get_artist_genres_api_error(self, ai_client_with_key):
        """Test get_artist_genres raises APIConnectionError on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection timeout")
            
            with pytest.raises(APIConnectionError):
                ai_client_with_key.get_artist_genres("Artist")

    def test_api_connection_refused(self, ai_client_with_key):
        """Test raises APIConnectionError on connection refused."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = ConnectionRefusedError("Connection refused")
            
            with pytest.raises(APIConnectionError):
                ai_client_with_key.infer_tags("file.mp3")


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
        """Test that invalid JSON raises APIParseError."""
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

        with pytest.raises(APIParseError):
            ai_client_with_key.infer_tags("file.mp3")


# ============================================================================
# Test: Timeout handling
# ============================================================================
class TestTimeoutHandling:
    """Tests for timeout handling in API calls."""

    def test_timeout_error(self, ai_client_with_key):
        """Test raises APITimeoutError on timeout."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Request timed out")
            
            with pytest.raises(APITimeoutError):
                ai_client_with_key.infer_tags("file.mp3")

    def test_socket_timeout(self, ai_client_with_key):
        """Test raises APITimeoutError on socket timeout."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Socket timeout")
            
            with pytest.raises(APITimeoutError):
                ai_client_with_key.get_similar_artists("Artist")


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

            # Now make a call - need to provide proper mock response
            mock_response = MagicMock()
            api_response = {
                "choices": [
                    {
                        "message": {
                            "content": '{"artist": "Test", "title": "Title"}'
                        }
                    }
                ]
            }
            mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
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
        """Test that response parsing errors raise APIParseError."""
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
            
            # Should raise APIParseError
            with pytest.raises(APIParseError):
                ai_client_with_key.infer_tags("file.mp3")



    def test_extract_result_exception_path(self, ai_client_with_key):
        """Test _extract_result raises APIParseError on exception."""
        # Mock response that causes exception during extraction
        mock_response_data = {
            "choices": []  # Empty choices will cause IndexError
        }
        
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Should raise APIParseError
            with pytest.raises(APIParseError):
                ai_client_with_key.infer_tags("file.mp3")


# ============================================================================
# Test: analyze_folder_organization()
# ============================================================================
class TestAnalyzeFolderOrganization:
    """Tests for AIClient.analyze_folder_organization() method."""

    def test_analyze_folder_organization_fallback(self, ai_client_no_key):
        """Test analyze_folder_organization returns empty results when no API key."""
        folder_structure = {
            "/music/Rock": [
                {"file": "song1.mp3", "artist": "Iron Maiden"},
            ],
        }
        artist_genres = {"Iron Maiden": ["heavy metal"]}
        
        result = ai_client_no_key.analyze_folder_organization(folder_structure, artist_genres)
        
        assert "moves" in result
        assert "renames" in result
        assert result == {"moves": [], "renames": []}

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_analyze_folder_organization_valid_json(self, mock_urlopen, ai_client_with_key):
        """Test analyze_folder_organization with valid JSON response."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "moves": [
                                {"from": "/music/Rock/song1.mp3", "to": "/music/Heavy Metal/song1.mp3", "reason": "Artist is heavy metal"}
                            ],
                            "renames": []
                        })
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        folder_structure = {
            "/music/Rock": [{"file": "song1.mp3", "artist": "Iron Maiden"}]
        }
        artist_genres = {"Iron Maiden": ["heavy metal"]}
        result = ai_client_with_key.analyze_folder_organization(folder_structure, artist_genres)

        assert "moves" in result
        assert "renames" in result
        assert len(result["moves"]) == 1
        assert result["moves"][0]["from"] == "/music/Rock/song1.mp3"
        mock_urlopen.assert_called_once()

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_analyze_folder_organization_markdown_code_blocks(self, mock_urlopen, ai_client_with_key):
        """Test analyze_folder_organization handles markdown code blocks in response."""
        mock_response = MagicMock()
        # LLM returns JSON wrapped in markdown code blocks
        content_with_blocks = """```json
{
  "moves": [
    {"from": "/music/Rock/song1.mp3", "to": "/music/Metal/song1.mp3", "reason": "Genre mismatch"}
  ],
  "renames": []
}
```"""
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": content_with_blocks
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        folder_structure = {
            "/music/Rock": [{"file": "song1.mp3", "artist": "Iron Maiden"}]
        }
        artist_genres = {"Iron Maiden": ["heavy metal"]}
        result = ai_client_with_key.analyze_folder_organization(folder_structure, artist_genres)

        # Should parse successfully despite markdown blocks
        assert "moves" in result
        assert "renames" in result
        assert len(result["moves"]) == 1

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_analyze_folder_organization_invalid_json_returns_empty(self, mock_urlopen, ai_client_with_key):
        """Test analyze_folder_organization returns empty results on invalid JSON."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": "This is not valid JSON at all"
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        folder_structure = {
            "/music/Rock": [{"file": "song1.mp3", "artist": "Iron Maiden"}]
        }
        artist_genres = {"Iron Maiden": ["heavy metal"]}
        
        # Should NOT raise, should return empty results
        result = ai_client_with_key.analyze_folder_organization(folder_structure, artist_genres)
        
        assert result == {"moves": [], "renames": []}

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_analyze_folder_organization_empty_response_returns_empty(self, mock_urlopen, ai_client_with_key):
        """Test analyze_folder_organization returns empty results on empty response."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        folder_structure = {
            "/music/Rock": [{"file": "song1.mp3", "artist": "Iron Maiden"}]
        }
        artist_genres = {"Iron Maiden": ["heavy metal"]}
        
        result = ai_client_with_key.analyze_folder_organization(folder_structure, artist_genres)
        
        assert result == {"moves": [], "renames": []}

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_analyze_folder_organization_prompt_includes_data(self, mock_urlopen, ai_client_with_key):
        """Test that prompt includes folder structure and artist genres."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"moves": [], "renames": []})
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        folder_structure = {
            "/music/Rock": [{"file": "song1.mp3", "artist": "Iron Maiden"}]
        }
        artist_genres = {"Iron Maiden": ["heavy metal"]}
        
        ai_client_with_key.analyze_folder_organization(folder_structure, artist_genres)
        
        # Verify the request was made
        mock_urlopen.assert_called_once()
        # Get the request data to check prompt content
        call_args = mock_urlopen.call_args
        req = call_args[0][0]  # First positional arg is the Request object
        request_body = json.loads(req.data.decode('utf-8'))
        user_content = request_body["messages"][1]["content"]
        
        # Verify prompt includes the folder structure and artist genres
        assert "/music/Rock" in user_content
        assert "Iron Maiden" in user_content
        assert "heavy metal" in user_content

    def test_analyze_folder_organization_api_error_returns_empty(self, ai_client_with_key):
        """Test analyze_folder_organization returns empty results on API error."""
        with patch('musichouse.ai_client.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection error")

            folder_structure = {
                "/music/Rock": [{"file": "song1.mp3", "artist": "Iron Maiden"}]
            }
            artist_genres = {"Iron Maiden": ["heavy metal"]}
            
            # Should NOT raise, should return empty results
            result = ai_client_with_key.analyze_folder_organization(folder_structure, artist_genres)
            
            assert result == {"moves": [], "renames": []}


# ============================================================================
# Test: get_similar_artists_json validation edge cases
# ============================================================================

class TestSimilarArtistsJsonReasonValidation:
    """Tests for reason field validation in get_similar_artists_json."""

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_reason_null(self, mock_urlopen, ai_client_with_key):
        """Test validation when reason is null."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"artist": "Artist A", "reason": null}]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # null reason should raise TypeError (not a string)
        with pytest.raises(TypeError, match="'reason' must be string"):
            ai_client_with_key.get_similar_artists_json("Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_get_similar_artists_json_reason_whitespace(self, mock_urlopen, ai_client_with_key):
        """Test validation when reason is whitespace."""
        mock_response = MagicMock()
        api_response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"artist": "Artist A", "reason": "   "}]'
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = ai_client_with_key.get_similar_artists_json("Artist")
        
        # Whitespace reason should be stripped to empty string
        assert result == [{"artist": "Artist A", "reason": ""}]


# ============================================================================
# Test: _extract_result fallback paths
# ============================================================================
def test_extract_result_invalid_json_raises_error(ai_client_no_key):
    """Test _extract_result raises APIParseError on invalid JSON."""
    mock_response = MagicMock()
    mock_response.text = "This is not JSON at all"
    
    with patch.object(ai_client_no_key, '_call_api', return_value=mock_response), pytest.raises(APIParseError):
        ai_client_no_key._extract_result(mock_response)


def test_extract_result_object_then_array_fallback(ai_client_no_key):
    """Test _extract_result tries object then array fallback."""
    # Invalid object, valid array - but needs choices structure
    # The response is already parsed dict, not raw text
    mock_response = {
        "choices": [{
            "message": {
                "content": 'Some text {invalid json} more text [{"artist": "Test"}]'
            }
        }]
    }
    
    with patch.object(ai_client_no_key, '_call_api', return_value=mock_response):
        result = ai_client_no_key._extract_result(mock_response)
        assert result == [{"artist": "Test"}]


def test_extract_result_key_error_raises(ai_client_no_key):
    """Test _extract_result raises APIParseError on KeyError."""
    mock_response = {"wrong_key": "value"}  # Missing choices
    
    with pytest.raises(APIParseError, match="no choices"):
        ai_client_no_key._extract_result(mock_response)


def test_extract_result_array_json_decode_error(ai_client_no_key):
    """Test _extract_result handles array JSON decode error."""
    # Valid choices, invalid object JSON, invalid array JSON
    mock_response = {
        "choices": [{
            "message": {
                "content": 'Some text {invalid} more text [also invalid]'
            }
        }]
    }
    
    with pytest.raises(APIParseError, match="no valid JSON"):
        ai_client_no_key._extract_result(mock_response)


def test_extract_result_index_error_raises(ai_client_no_key):
    """Test _extract_result raises APIParseError on IndexError."""
    mock_response = {"choices": []}  # Empty choices
    
    with pytest.raises(APIParseError, match="no choices"):
        ai_client_no_key._extract_result(mock_response)


def test_extract_result_nested_key_error(ai_client_no_key):
    """Test _extract_result raises APIParseError on nested KeyError."""
    # Has choices but missing message or content
    mock_response = {"choices": [{"wrong_key": "value"}]}
    
    with pytest.raises(APIParseError, match="Failed to parse"):
        ai_client_no_key._extract_result(mock_response)


# ============================================================================
# Test: analyze_folder_organization edge cases
# ============================================================================
def test_analyze_folder_organization_wrong_type(ai_client_no_key):
    """Test analyze_folder_organization handles wrong result type."""
    mock_response = MagicMock()
    mock_response.text = '["not", "a", "dict"]'  # Array instead of dict
    
    with patch.object(ai_client_no_key, '_call_api', return_value=mock_response):
        result = ai_client_no_key.analyze_folder_organization({}, {})
        assert result == {"moves": [], "renames": []}
