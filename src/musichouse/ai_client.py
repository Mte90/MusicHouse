"""AI client for MusicHouse."""

import json
import socket
import urllib.error
import urllib.request
from typing import Dict, Any, Optional, List

from musichouse import logging
from musichouse import config

logger = logging.get_logger(__name__)


class AIClient:
    """Client for OpenAI-compatible API."""

    def __init__(
        self, 
        endpoint: Optional[str] = None, 
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.endpoint = endpoint or config.get_endpoint()
        self.model = model or config.get_model()
        self.api_key = api_key or config.get_api_key()

    def infer_tags(self, filename: str) -> Dict[str, str]:
        """Infer artist and title from filename using AI."""
        prompt = f'Analyze: "{filename}". Return JSON with artist and title.'
        return self._call_api(prompt)

    def get_similar_artists(self, artist: str) -> List[str]:
        """Get similar artists."""
        prompt = f'Find 5-10 artists like "{artist}". Return JSON array.'
        result = self._call_api(prompt)
        # result can be a list (from array response) or dict
        if isinstance(result, list):
            return result
        return result.get("artists", [])

    def get_artist_genres(self, artist: str) -> List[str]:
        """Get artist genres."""
        prompt = f'What genres is "{artist}"? Return JSON array.'
        result = self._call_api(prompt)
        # result can be a list (from array response) or dict
        if isinstance(result, list):
            return result
        return result.get("genres", [])

    def _call_api(self, prompt: str) -> Dict[str, Any]:
        """Call the API endpoint."""
        if not self.api_key:
            logger.warning("No API key configured")
            return self._get_fallback_response(prompt)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.endpoint, 
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return self._extract_result(result)
                
        except urllib.error.HTTPError as e:
            # API returned an error status code (401, 403, 500, etc.)
            error_msg = f"API error: {e.code} {e.reason}"
            logger.error(error_msg)
            return {"error": error_msg}
            
        except TimeoutError as e:
            # Request timed out
            error_msg = "Request timed out after 30s"
            logger.error(error_msg)
            return {"error": error_msg}
            
        except socket.timeout as e:
            # Socket timeout
            error_msg = "Request timed out after 30s"
            logger.error(error_msg)
            return {"error": error_msg}
            
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            # Network errors (connection refused, DNS failure, etc.)
            error_msg = f"Network error: {e.reason}" if hasattr(e, 'reason') else f"Network error: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
            
        except json.JSONDecodeError as e:
            # Invalid JSON in API response
            error_msg = f"Failed to parse AI response: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
            
        except Exception as e:
            # Catch-all for any other unexpected errors
            error_msg = f"AI service error: {e}"
            logger.error(error_msg)
            return {"error": error_msg}

    def _extract_result(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response robustly."""
        try:
            if "choices" not in response or not response["choices"]:
                error_msg = "Failed to parse AI response: no choices in response"
                logger.error(error_msg)
                return {"error": error_msg}
                
            content = response["choices"][0]["message"]["content"]
            
            # Primary: use raw_decode which properly handles nested JSON
            decoder = json.JSONDecoder()
            result, _ = decoder.raw_decode(content)
            return result
        except json.JSONDecodeError:
            # Fallback: try to find JSON-like pattern with regex
            import re
            
            # Try object first
            obj_match = re.search(r'\{.*\}', content, re.DOTALL)
            if obj_match:
                try:
                    return json.loads(obj_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Try array
            arr_match = re.search(r'\[.*\]', content, re.DOTALL)
            if arr_match:
                try:
                    return json.loads(arr_match.group())
                except json.JSONDecodeError:
                    pass
            
            error_msg = "Failed to parse AI response: no valid JSON found"
            logger.error(error_msg)
            return {"error": error_msg}
        except (KeyError, IndexError) as e:
            error_msg = f"Failed to parse AI response: {e}"
            logger.error(error_msg)
            return {"error": error_msg}

    def _get_fallback_response(self, prompt: str) -> Dict[str, Any]:
        """Generate fallback response when API fails."""
        if "similar" in prompt.lower() or "artists like" in prompt.lower():
            return {"artists": ["Unknown Artist"]}
        elif "genre" in prompt.lower():
            return {"genres": ["Unknown Genre"]}
        return {"artist": "Unknown", "title": "Unknown"}
