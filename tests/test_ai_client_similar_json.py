"""Additional tests for AIClient.get_similar_artists_json()."""

import json
from unittest.mock import MagicMock, patch

import pytest

from musichouse.ai_client import AIClient
from musichouse.error_handling import APIParseError


@pytest.fixture
def ai_client_with_key():
    """Create AIClient with fake API key."""
    with patch('musichouse.ai_client.config.get_api_key', return_value='fake-key-for-testing'), \
         patch('musichouse.ai_client.config.get_endpoint', return_value='http://localhost:8080'), \
         patch('musichouse.ai_client.config.get_model', return_value='test-model'):
        return AIClient()


class TestGetSimilarArtistsJson:
    """Tests for AIClient.get_similar_artists_json()."""

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_valid_json_array_success(self, mock_urlopen, ai_client_with_key):
        """Test successful parsing of valid JSON array response."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"artist": "Artist A", "reason": "Similar"}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = ai_client_with_key.get_similar_artists_json("Test Artist")
        
        assert len(result) == 1
        assert result[0] == {"artist": "Artist A", "reason": "Similar"}

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_response_closed_on_success(self, mock_urlopen, ai_client_with_key):
        """Test that HTTP response is closed after successful read."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"artist": "Artist A", "reason": "Test"}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        ai_client_with_key.get_similar_artists_json("Test Artist")
        
        mock_response.__exit__.assert_called_once()

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_invalid_json_raises(self, mock_urlopen, ai_client_with_key):
        """Test that invalid JSON raises APIParseError."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": "This is not valid JSON at all"}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(APIParseError):
            ai_client_with_key.get_similar_artists_json("Test Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_non_list_response_raises(self, mock_urlopen, ai_client_with_key):
        """Test that non-list response raises TypeError."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": '{"artist": "Artist A", "reason": "Test"}'}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(TypeError, match="Expected list response"):
            ai_client_with_key.get_similar_artists_json("Test Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_item_not_dict_raises(self, mock_urlopen, ai_client_with_key):
        """Test that non-dict item raises TypeError."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps(["Artist A", "Artist B"])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(TypeError, match="Item 0 is not a dict"):
            ai_client_with_key.get_similar_artists_json("Test Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_missing_artist_field_raises(self, mock_urlopen, ai_client_with_key):
        """Test that missing 'artist' field raises ValueError."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"reason": "Test reason"}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(ValueError, match="missing required 'artist' field"):
            ai_client_with_key.get_similar_artists_json("Test Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_empty_artist_string_raises(self, mock_urlopen, ai_client_with_key):
        """Test that empty artist string raises ValueError."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"artist": "", "reason": "Test"}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(ValueError, match="'artist' must be non-empty string"):
            ai_client_with_key.get_similar_artists_json("Test Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_reason_must_be_string(self, mock_urlopen, ai_client_with_key):
        """Test that non-string reason raises TypeError."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"artist": "Artist A", "reason": 123}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(TypeError, match="'reason' must be string"):
            ai_client_with_key.get_similar_artists_json("Test Artist")

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_reason_optional_defaults_to_empty(self, mock_urlopen, ai_client_with_key):
        """Test that missing reason defaults to empty string."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"artist": "Artist A"}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = ai_client_with_key.get_similar_artists_json("Test Artist")
        
        assert result == [{"artist": "Artist A", "reason": ""}]

    @patch('musichouse.ai_client.urllib.request.urlopen')
    def test_whitespace_trimmed(self, mock_urlopen, ai_client_with_key):
        """Test that whitespace is trimmed from artist and reason."""
        mock_response = MagicMock()
        api_response = {
            "choices": [{"message": {"content": json.dumps([{"artist": "  Artist A  ", "reason": "  Test  "}])}}]
        }
        mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = ai_client_with_key.get_similar_artists_json("Test Artist")
        
        assert result == [{"artist": "Artist A", "reason": "Test"}]
