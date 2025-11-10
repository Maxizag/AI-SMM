"""Idempotency middleware for preventing duplicate requests"""

import json
import logging
import hashlib
from typing import Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Idempotency middleware using Idempotency-Key header

    Prevents duplicate processing of requests by caching responses
    based on Idempotency-Key header.

    Uses in-memory storage (for production, use Redis)

    Headers:
    - Idempotency-Key: Client-generated unique key (UUID recommended)

    Behavior:
    - If Idempotency-Key is provided and matches a previous request,
      return the cached response
    - If Idempotency-Key is new, process request normally and cache response
    - Cached responses expire after 24 hours

    Note: Only applies to POST/PUT/PATCH methods
    """

    def __init__(
        self,
        app,
        cache_ttl_hours: int = 24,
        max_cache_size: int = 10000
    ):
        """
        Initialize idempotency middleware

        Args:
            app: FastAPI application
            cache_ttl_hours: Cache time-to-live in hours
            max_cache_size: Maximum number of cached responses
        """
        super().__init__(app)
        self.cache_ttl_hours = cache_ttl_hours
        self.max_cache_size = max_cache_size

        # In-memory cache: {idempotency_key: (response_data, expiry_time)}
        # For production, replace with Redis
        self.cache: Dict[str, Tuple[dict, datetime]] = {}

    async def dispatch(self, request: Request, call_next):
        """
        Process request with idempotency support

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response (cached or new)
        """
        # Only apply to mutation methods
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)

        # Extract Idempotency-Key header
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            # No idempotency key, process normally
            return await call_next(request)

        # Cleanup expired entries
        self._cleanup_expired()

        # Check cache
        cached_response = self._get_cached_response(idempotency_key)

        if cached_response:
            logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
            return JSONResponse(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers={
                    **cached_response["headers"],
                    "X-Idempotency-Replay": "true"
                }
            )

        # Process request normally
        response = await call_next(request)

        # Cache successful responses (2xx status codes)
        if 200 <= response.status_code < 300:
            await self._cache_response(idempotency_key, response)

        return response

    def _get_cached_response(self, key: str) -> Optional[dict]:
        """
        Get cached response for idempotency key

        Args:
            key: Idempotency key

        Returns:
            Cached response data or None
        """
        if key in self.cache:
            response_data, expiry = self.cache[key]

            # Check if expired
            if datetime.utcnow() < expiry:
                return response_data
            else:
                # Remove expired entry
                del self.cache[key]

        return None

    async def _cache_response(self, key: str, response: Response):
        """
        Cache response for idempotency key

        Args:
            key: Idempotency key
            response: Response to cache
        """
        # Limit cache size
        if len(self.cache) >= self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            # For production with Redis, use TTL
            oldest_keys = sorted(
                self.cache.items(),
                key=lambda x: x[1][1]
            )[:100]  # Remove 100 oldest
            for old_key, _ in oldest_keys:
                del self.cache[old_key]

        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            body_json = json.loads(body.decode())
        except:
            # Non-JSON response, skip caching
            logger.warning(f"Cannot cache non-JSON response for key: {key}")
            return

        # Cache response data
        expiry = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)

        self.cache[key] = (
            {
                "body": body_json,
                "status_code": response.status_code,
                "headers": dict(response.headers)
            },
            expiry
        )

        logger.info(f"Cached response for idempotency key: {key}")

    def _cleanup_expired(self):
        """
        Remove expired entries from cache

        Called before each request to prevent memory leaks
        """
        current_time = datetime.utcnow()

        expired_keys = [
            key for key, (_, expiry) in self.cache.items()
            if expiry <= current_time
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


# Production implementation with Redis:
#
# import redis
# from redis import Redis
#
# class RedisIdempotency:
#     def __init__(self, redis_client: Redis, ttl_hours: int = 24):
#         self.redis = redis_client
#         self.ttl_seconds = ttl_hours * 3600
#
#     def get_cached_response(self, key: str) -> Optional[dict]:
#         cache_key = f"idempotency:{key}"
#         data = self.redis.get(cache_key)
#
#         if data:
#             return json.loads(data)
#
#         return None
#
#     def cache_response(self, key: str, response_data: dict):
#         cache_key = f"idempotency:{key}"
#         self.redis.setex(
#             cache_key,
#             self.ttl_seconds,
#             json.dumps(response_data)
#         )
