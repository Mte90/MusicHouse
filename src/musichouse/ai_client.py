"""AI client for MusicHouse."""

import json
import urllib.error
import urllib.request
from typing import Any

from musichouse import config
from musichouse import log_setup as logging
from musichouse.error_handling import APIConnectionError, APIParseError, APITimeoutError

logger = logging.get_logger(__name__)


class AIClient:
    """Client for OpenAI-compatible API."""

    def __init__(
        self, 
        endpoint: str | None = None, 
        model: str | None = None,
        api_key: str | None = None
    ):
        self.endpoint = endpoint or config.get_endpoint()
        self.model = model or config.get_model()
        self.api_key = api_key or config.get_api_key()

    def infer_tags(self, filename: str) -> dict[str, str]:
        """Infer artist and title from filename using AI."""
        prompt = f'Analyze: "{filename}". Return JSON with artist and title.'
        return self._call_api(prompt)

    def get_similar_artists(self, artist: str) -> list[str]:
        """Get similar artists."""
        prompt = f'Find 5-10 artists like "{artist}". Return JSON array.'
        result = self._call_api(prompt)
        # result can be a list (from array response) or dict
        if isinstance(result, list):
            return result
        return result.get("artists", [])

    def get_artist_genres(self, artist: str) -> list[str]:
        """Get artist genres."""
        prompt = f'What genres is "{artist}"? Return JSON array.'
        result = self._call_api(prompt)
        # result can be a list (from array response) or dict
        if isinstance(result, list):
            return result
        return result.get("genres", [])

    def _call_api(self, prompt: str, system_prompt: str | None = None) -> dict[str, Any]:
        """Call the API endpoint."""
        if not self.api_key:
            logger.warning("No API key configured")
            return self._get_fallback_response(prompt)

        system_content = system_prompt or "Return valid JSON only."
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
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
            try:
                raise APIConnectionError(error_msg)
            finally:
                e.close()
            
        except TimeoutError:
            # Request timed out
            error_msg = "Request timed out after 30s"
            logger.error(error_msg)
            raise APITimeoutError(error_msg)
            
            
        except urllib.error.URLError as e:
            # Network errors (connection refused, DNS failure, etc.)
            error_msg = f"Cannot connect to API: {e.reason}" if hasattr(e, 'reason') else f"Cannot connect to API: {e}"
            logger.error(error_msg)
            raise APIConnectionError(error_msg)
            
        except ConnectionRefusedError:
            # Connection refused
            error_msg = "Cannot connect to API: Connection refused"
            logger.error(error_msg)
            raise APIConnectionError(error_msg)
            
        except (ConnectionError, OSError) as e:
            # Connection errors
            error_msg = f"Cannot connect to API: {e}"
            logger.error(error_msg)
            raise APIConnectionError(error_msg)
            
        except json.JSONDecodeError as e:
            # Invalid JSON in API response
            error_msg = f"Failed to parse AI response: {e}"
            logger.error(error_msg)
            raise APIParseError(error_msg)
            
        except APIParseError:
            # Re-raise parse errors as-is
            raise
            
        except Exception as e:  # noqa: BLE001
            # Catch-all for any other unexpected errors
            error_msg = f"AI service error: {e}"
            logger.error(error_msg)
            raise APIConnectionError(error_msg)
            


    def _extract_result(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract JSON from LLM response robustly."""
        try:
            if "choices" not in response or not response["choices"]:
                error_msg = "Failed to parse AI response: no choices in response"
                logger.error(error_msg)
                raise APIParseError(error_msg)
                
            content = response["choices"][0]["message"]["content"]
            
            # Primary: use raw_decode which properly handles nested JSON
            decoder = json.JSONDecoder()
            result, _ = decoder.raw_decode(content)
            return result
        except APIParseError:
            raise
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
            raise APIParseError(error_msg)
        except (KeyError, IndexError) as e:
            error_msg = f"Failed to parse AI response: {e}"
            logger.error(error_msg)
            raise APIParseError(error_msg)

    def analyze_folder_organization(
        self, folder_structure: dict[str, list[dict[str, str]]], artist_genres: dict[str, list[str]]
    ) -> dict[str, list[dict[str, str]]]:
        """
        Ask the LLM to suggest file moves and folder renames based on folder structure
        and artist genre data from MusicBrainz.

        Args:
            folder_structure: dict mapping folder paths to lists of files with metadata.
                Example: {
                    "/music/Rock": [
                        {"file": "song1.mp3", "artist": "Iron Maiden"},
                        {"file": "song2.mp3", "artist": "Judas Priest"},
                    ],
                    "/music/Metallica": [
                        {"file": "song3.mp3", "artist": "Metallica"},
                    ],
                }
            artist_genres: dict mapping artist names to genre lists.
                Example: {"Iron Maiden": ["heavy metal", "NWOBHM"], ...}

        Returns:
            dict with keys "moves" and "renames":
            {
                "moves": [{"from": str, "to": str, "reason": str}, ...],
                "renames": [{"from": str, "to": str, "reason": str}, ...],
            }
        """
        system_prompt = "You are a music library organizer. Analyze the folder structure and artist genres. Suggest file moves and folder renames. Return valid JSON with 'moves' and 'renames' arrays only, no explanation."
        
        user_prompt = f"""Analyze this music library structure and suggest organization improvements.

Folder Structure:
{json.dumps(folder_structure, indent=2)}

Artist Genres:
{json.dumps(artist_genres, indent=2)}

Return JSON with "moves" and "renames" arrays. Each move has "from", "to", "reason". Each rename has "from", "to", "reason"."""
        
        try:
            result = self._call_api(user_prompt, system_prompt)
            # Ensure result has the expected structure
            if not isinstance(result, dict):
                logger.warning("Unexpected result type, returning empty results")
                return {"moves": [], "renames": []}
            return {
                "moves": result.get("moves", []),
                "renames": result.get("renames", [])
            }
        except Exception:  # noqa: BLE001
            logger.warning("Failed to get organization suggestions, returning empty results")
            return {"moves": [], "renames": []}

    def _get_fallback_response(self, prompt: str) -> dict[str, Any]:
        """Generate fallback response when API fails."""
        if "similar" in prompt.lower() or "artists like" in prompt.lower():
            return {"artists": ["Unknown Artist"]}
        elif "genre" in prompt.lower():
            return {"genres": ["Unknown Genre"]}
        return {"artist": "Unknown", "title": "Unknown"}
