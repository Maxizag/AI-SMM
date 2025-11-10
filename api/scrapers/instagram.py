"""Instagram content scraper"""

from typing import List, Dict, Any, Optional
import re
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)


class InstagramScraper(BaseScraper):
    """
    Scraper for Instagram public profiles

    Instagram scraping is challenging due to API restrictions.
    Options:
    1. Official Instagram Graph API (requires business account + app review)
    2. Unofficial libraries like instaloader (may break with IG updates)
    3. Web scraping (fragile, may be blocked)

    For T6: MOCK implementation
    Real implementation would likely use instaloader library

    URL formats supported:
    - https://www.instagram.com/username/
    - https://instagram.com/username
    """

    def __init__(self, url: str, session_file: Optional[str] = None):
        """
        Initialize Instagram scraper

        Args:
            url: Instagram profile URL
            session_file: Path to instaloader session file (for authenticated scraping)
        """
        super().__init__(url)
        self.session_file = session_file
        self.handle = self.extract_handle_from_url(url)

    def _get_platform_name(self) -> str:
        return "instagram"

    def extract_handle_from_url(self, url: str) -> Optional[str]:
        """
        Extract username from Instagram URL

        Examples:
            https://www.instagram.com/username/ -> username
            https://instagram.com/username -> username
        """
        # Extract from instagram.com URL
        match = re.search(r'instagram\.com/([^/?]+)', url)
        if match:
            username = match.group(1)
            # Filter out Instagram paths like 'p', 'reel', 'tv'
            if username not in ['p', 'reel', 'tv', 'stories', 'explore']:
                return username

        return None

    async def verify(self) -> Dict[str, Any]:
        """
        Verify Instagram profile accessibility

        For T6: MOCK implementation
        Real implementation would:
        1. Use instaloader to load profile
        2. Check if profile exists and is public
        3. Get post count from profile metadata
        4. Return verification status

        Returns verification status
        """
        logger.info(f"Verifying Instagram profile: {self.handle}")

        if not self.handle:
            return {
                "status": "INVALID_URL",
                "message": "Could not extract username from URL"
            }

        # MOCK: Return success for demo
        # Real implementation would use instaloader:
        # import instaloader
        # L = instaloader.Instaloader()
        # try:
        #     if self.session_file:
        #         L.load_session_from_file(username, self.session_file)
        #     profile = instaloader.Profile.from_username(L.context, self.handle)
        #     if profile.is_private:
        #         return {"status": "CLOSED", "message": "Profile is private"}
        #     posts_count = profile.mediacount
        #     if posts_count < 50:
        #         return {"status": "LOW_CONTENT", "posts_count": posts_count}
        # except instaloader.exceptions.ProfileNotExistsException:
        #     return {"status": "INVALID_URL", "message": "Profile not found"}

        return {
            "status": "OK",
            "message": "Instagram profile verified successfully",
            "posts_count": 85,
            "handle": self.handle,
            "is_private": False
        }

    async def scrape(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Scrape posts from Instagram profile

        For T6: MOCK implementation
        Real implementation would:
        1. Use instaloader to get profile posts
        2. Iterate through posts up to limit
        3. Extract caption, media URLs, engagement stats
        4. Normalize to standard format

        Args:
            limit: Maximum number of posts to scrape

        Returns:
            List of normalized post dictionaries
        """
        logger.info(f"Scraping {limit} posts from Instagram: {self.handle}")

        # MOCK: Return sample posts
        # Real implementation would use instaloader:
        # import instaloader
        # L = instaloader.Instaloader()
        # if self.session_file:
        #     L.load_session_from_file(username, self.session_file)
        # profile = instaloader.Profile.from_username(L.context, self.handle)
        #
        # posts = []
        # for post in profile.get_posts():
        #     if len(posts) >= limit:
        #         break
        #
        #     media = []
        #     if post.typename == 'GraphImage':
        #         media.append({"type": "image", "url": post.url})
        #     elif post.typename == 'GraphVideo':
        #         media.append({"type": "video", "url": post.video_url})
        #     elif post.typename == 'GraphSidecar':
        #         for node in post.get_sidecar_nodes():
        #             if node.is_video:
        #                 media.append({"type": "video", "url": node.video_url})
        #             else:
        #                 media.append({"type": "image", "url": node.display_url})
        #
        #     normalized_post = {
        #         "platform_post_id": post.shortcode,
        #         "author_handle": self.handle,
        #         "posted_at": post.date_utc,
        #         "text": post.caption or "",
        #         "media": media,
        #         "reactions": {
        #             "likes": post.likes,
        #             "comments": post.comments,
        #             "views": post.video_view_count if post.is_video else 0,
        #             "shares": 0  # Instagram doesn't provide share count
        #         },
        #         "link": f"https://www.instagram.com/p/{post.shortcode}/",
        #         "raw": {}
        #     }
        #     posts.append(normalized_post)

        posts = []
        for i in range(min(limit, 100)):
            posts.append({
                "platform_post_id": f"ABC{i:04d}XYZ",
                "author_handle": self.handle,
                "posted_at": None,  # Would be post.date_utc
                "text": f"Sample Instagram post {i + 1} #sample #demo",
                "media": [{"type": "image", "url": f"https://example.com/img{i}.jpg"}],
                "reactions": {
                    "likes": 100 + i * 5,
                    "comments": 20 + i,
                    "views": 0,
                    "shares": 0
                },
                "link": f"https://www.instagram.com/p/ABC{i:04d}XYZ/",
                "raw": {}
            })

        logger.info(f"Scraped {len(posts)} posts from Instagram")
        return posts
