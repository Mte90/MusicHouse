"""AI client for MusicHouse."""

import json
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
                
        except Exception as e:
            logger.error(f"API error: {e}")
            return self._get_fallback_response(prompt)

    def _extract_result(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract result from API response."""
        try:
            content = response["choices"][0]["message"]["content"]
            # Find JSON in response (handle both objects {} and arrays [])
            start_obj = content.find('{')
            end_obj = content.rfind('}') + 1
            start_arr = content.find('[')
            end_arr = content.rfind(']') + 1
            
            # Try object first
            if start_obj >= 0 and end_obj > start_obj:
                return json.loads(content[start_obj:end_obj])
            # Try array
            elif start_arr >= 0 and end_arr > start_arr:
                return json.loads(content[start_arr:end_arr])
            return {"error": "Parse failed"}
        except Exception as e:
            logger.error(f"Response parse error: {e}")
            return {"error": str(e)}

    def _get_fallback_response(self, prompt: str) -> Dict[str, Any]:
        """Generate fallback response when API fails."""
        if "similar" in prompt.lower() or "artists like" in prompt.lower():
            return {"artists": ["Unknown Artist"]}
        elif "genre" in prompt.lower():
            return {"genres": ["Unknown Genre"]}
        return {"artist": "Unknown", "title": "Unknown"}
