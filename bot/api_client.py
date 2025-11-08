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

    async def verify_source(
        self,
        user_id: str,
        url: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify a source URL before saving

        Args:
            user_id: User UUID
            url: URL to verify
            access_token: User's JWT token

        Returns:
            Verification result with status: OK, CLOSED, LOW_CONTENT, DUPLICATE, INVALID_URL
            or None if failed
        """
        try:
            api_url = f"{self.base_url}/sources/verify"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "user_id": user_id,
                "url": url
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Source verified: {url}, status: {data['status']}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to verify source: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying source: {e}")
            return None

    async def scrape_source(
        self,
        source_id: str,
        user_id: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Start scraping posts from a source

        Args:
            source_id: Source UUID
            user_id: User UUID
            access_token: User's JWT token

        Returns:
            Scrape result with status: SUCCESS, IN_PROGRESS, ERROR
            or None if failed
        """
        try:
            api_url = f"{self.base_url}/ingest/scrape"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "source_id": source_id,
                "user_id": user_id
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Scraping completed: {source_id}, posts: {data.get('posts_collected', 0)}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to scrape source: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping source: {e}")
            return None

    async def create_source(
        self,
        user_id: str,
        platform: str,
        url: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a content source

        Args:
            user_id: User UUID
            platform: Social media platform name
            url: URL to the profile/content
            access_token: User's JWT token

        Returns:
            Created source data or None if failed
        """
        try:
            api_url = f"{self.base_url}/sources"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "user_id": user_id,
                "platform": platform,
                "url": url
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Source created: {data['id']}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to create source: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating source: {e}")
            return None

    async def create_brief(
        self,
        user_id: str,
        goal: str,
        audience: str,
        tone: str,
        topic: str,
        frequency: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a content brief (Branch 1: experienced users)

        Returns:
            Created brief data or None if failed
        """
        try:
            api_url = f"{self.base_url}/briefs"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "user_id": user_id,
                "goal": goal,
                "audience": audience,
                "tone": tone,
                "topic": topic,
                "frequency": frequency
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Brief created: {data['id']}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to create brief: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating brief: {e}")
            return None

    async def create_style_seed(
        self,
        user_id: str,
        tone: str,
        goal: str,
        topic: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a style seed (Branch 2: beginners)

        Returns:
            Created style seed data or None if failed
        """
        try:
            api_url = f"{self.base_url}/style_seed"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "user_id": user_id,
                "tone": tone,
                "goal": goal,
                "topic": topic
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"StyleSeed created: {data['id']}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to create style seed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating style seed: {e}")
            return None

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
