import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class APIClient:
    """Client for interacting with AI-SMM API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)

    async def authenticate_telegram_user(
        self,
        tg_user_id: int,
        name: str,
        username: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate or register user via Telegram

        Returns:
            Dict with access_token and user data, or None if failed
        """
        try:
            url = f"{self.base_url}/auth/tg"
            payload = {
                "tg_user_id": tg_user_id,
                "name": name,
            }
            if username:
                payload["username"] = username

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            logger.info(f"User authenticated: tg_user_id={tg_user_id}, user_id={data['user']['id']}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"API authentication failed for tg_user_id={tg_user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return None

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
