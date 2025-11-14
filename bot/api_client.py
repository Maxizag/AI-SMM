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
        url: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify a source URL before saving (T6 spec)

        Args:
            url: URL to verify
            access_token: User's JWT token

        Returns:
            Verification result with handle, accessible, private, post_count, normalized_url, message
            or None if failed
        """
        # Detect platform from URL
        platform = self._detect_platform(url)
        if not platform:
            logger.error(f"Could not detect platform from URL: {url}")
            return None

        try:
            api_url = f"{self.base_url}/sources/verify"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "platform": platform,
                "url": url
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Source verified: {url}, handle: {data.get('handle')}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to verify source: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying source: {e}")
            return None

    def _detect_platform(self, url: str) -> Optional[str]:
        """Detect platform from URL"""
        url_lower = url.lower()

        if "t.me" in url_lower or "telegram.org" in url_lower or url.startswith("@"):
            return "telegram"
        elif "vk.com" in url_lower or "vkontakte" in url_lower:
            return "vk"
        elif "instagram.com" in url_lower or "instagr.am" in url_lower:
            return "instagram"

        return None

    async def start_scraping_job(
        self,
        user_id: str,
        source_ids: list,
        access_token: str,
        target_posts: int = 100,
        min_posts: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Start asynchronous scraping job (T6 spec)

        Args:
            user_id: User UUID
            source_ids: List of source UUIDs to scrape
            access_token: User's JWT token
            target_posts: Target number of posts (default: 100)
            min_posts: Minimum acceptable posts (default: 50)

        Returns:
            Dict with job_id and status: "queued", or None if failed
        """
        try:
            api_url = f"{self.base_url}/sources/v2"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "user_id": user_id,
                "source_ids": source_ids,
                "target_posts": target_posts,
                "min_posts": min_posts
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Scraping job created: job_id={data.get('job_id')}, status={data.get('status')}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to start scraping job: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error starting scraping job: {e}")
            return None

    async def get_job_status(
        self,
        job_id: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get scraping job status (T6 spec)

        Args:
            job_id: Job UUID
            access_token: User's JWT token

        Returns:
            Dict with job_id, status, progress, errors, recommendations
            or None if failed
        """
        try:
            api_url = f"{self.base_url}/ingest/status"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"job_id": job_id}

            response = await self.client.get(api_url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Job status fetched: job_id={job_id}, status={data.get('status')}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to get job status: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting job status: {e}")
            return None

    async def start_scraping_job(
        self,
        user_id: str,
        source_ids: list,
        access_token: str,
        target_posts: int = 100,
        min_posts: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Start asynchronous scraping job (T6 spec)

        Args:
            user_id: User UUID
            source_ids: List of source UUIDs to scrape
            access_token: User's JWT token
            target_posts: Target number of posts (default: 100)
            min_posts: Minimum acceptable posts (default: 50)

        Returns:
            Dict with job_id and status: "queued", or None if failed
        """
        try:
            api_url = f"{self.base_url}/ingest/scrape"
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "user_id": user_id,
                "source_ids": source_ids,
                "target_posts": target_posts,
                "min_posts": min_posts
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Scraping job created: job_id={data.get('job_id')}, status={data.get('status')}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to start scraping job: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error starting scraping job: {e}")
            return None

    async def get_job_status(
        self,
        job_id: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get scraping job status (T6 spec)

        Args:
            job_id: Job UUID
            access_token: User's JWT token

        Returns:
            Dict with job_id, status, progress, errors, recommendations
            or None if failed
        """
        try:
            api_url = f"{self.base_url}/ingest/status"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"job_id": job_id}

            response = await self.client.get(api_url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Job status fetched: job_id={job_id}, status={data.get('status')}")
            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to get job status: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting job status: {e}")
            return None

    # Legacy method for backward compatibility
    async def create_source(
        self,
        user_id: str,
        platform: str,
        url: str,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a content source (LEGACY - use create_source_v2 instead)

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
            logger.info(f"Source created (legacy): {data['id']}")
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
        access_token: str,
        completion: int = 1  # 0=не пройден, 1=пройден (default: 1)
    ) -> Optional[Dict[str, Any]]:
        """
        Create a content brief (Branch 1: experienced users) - T6.1

        Args:
            completion: 0 if placeholder (not completed), 1 if completed (default)

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
                "frequency": frequency,
                "completion": completion
            }

            response = await self.client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Brief created: {data['id']}, completion={completion}")
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
