import logging
import httpx
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger("evently.typesafe")


class TypeSafeService:
    """
    Isolated optional secondary service for structured event quality verification.
    Evently core does NOT depend on this service. If TypeSafe is disabled,
    unavailable, times out, or fails, the application continues operating normally.
    """

    def __init__(self, api_key: Optional[str] = None, enabled: Optional[bool] = None):
        self.api_key = api_key if api_key is not None else settings.TYPESAFE_API_KEY
        self.enabled = enabled if enabled is not None else settings.TYPESAFE_ENABLED
        self.endpoint = "https://api.typesafe.ai/v1/validate"  # Standard endpoint
        self.timeout = 1.0  # Strict 1-second timeout to prevent blocking

    def is_available(self) -> bool:
        """Returns True only if service is enabled and API key is configured."""
        return bool(self.enabled and self.api_key and self.api_key.strip())

    async def verify_event_submission(self, title: str, description: str) -> Dict[str, Any]:
        """
        Optional review of organizer-submitted event content.
        Fails completely gracefully: returns fallback validation if API is unreachable.
        """
        fallback_result = {
            "is_valid": True,
            "quality_score": 1.0,
            "flags": [],
            "source": "deterministic_fallback"
        }

        if not self.is_available():
            return fallback_result

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "task": "event_content_safety",
                    "input": {
                        "title": title[:200],
                        "description": description[:500]
                    }
                }
                response = await client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "is_valid": data.get("is_valid", True),
                        "quality_score": data.get("quality_score", 1.0),
                        "flags": data.get("flags", []),
                        "source": "typesafe_ai"
                    }
                else:
                    logger.warning(f"TypeSafe API returned status {response.status_code}, using fallback.")
                    return fallback_result
        except Exception as e:
            logger.warning(f"TypeSafe API request failed ({e}), using fallback.")
            return fallback_result


typesafe_service = TypeSafeService()
