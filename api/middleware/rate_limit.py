"""Rate limiting middleware"""

import time
import logging
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware

    Limits requests to 30 per minute per user
    Uses in-memory storage (for production, use Redis)

    Rate limit applies to authenticated endpoints only
    User is identified by user_id from JWT token
    """

    def __init__(self, app, requests_per_minute: int = 30):
        """
        Initialize rate limiter

        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute per user
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # seconds

        # In-memory storage: {user_id: [(timestamp, count), ...]}
        # For production, replace with Redis
        self.request_counts: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        """
        Process each request and apply rate limiting

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response (429 if rate limit exceeded, otherwise normal response)
        """
        # Extract user_id from request state (set by auth dependency)
        # For endpoints without authentication, skip rate limiting
        user_id = getattr(request.state, "user_id", None)

        if user_id:
            # Check rate limit
            is_allowed, remaining, reset_time = self._check_rate_limit(str(user_id))

            if not is_allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Maximum 30 requests per minute.",
                        "retry_after": int(reset_time - time.time())
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(reset_time)),
                        "Retry-After": str(int(reset_time - time.time()))
                    }
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(reset_time))

            return response

        # No authentication, skip rate limiting
        return await call_next(request)

    def _check_rate_limit(self, user_id: str) -> Tuple[bool, int, float]:
        """
        Check if user has exceeded rate limit

        Args:
            user_id: User identifier

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
        current_time = time.time()
        window_start = current_time - self.window_size

        # Get requests for this user
        user_requests = self.request_counts[user_id]

        # Remove requests outside current window
        user_requests = [req_time for req_time in user_requests if req_time > window_start]
        self.request_counts[user_id] = user_requests

        # Check if limit exceeded
        request_count = len(user_requests)

        if request_count >= self.requests_per_minute:
            # Rate limit exceeded
            oldest_request = min(user_requests)
            reset_time = oldest_request + self.window_size
            return False, 0, reset_time

        # Add current request
        user_requests.append(current_time)

        # Calculate remaining and reset time
        remaining = self.requests_per_minute - len(user_requests)
        reset_time = current_time + self.window_size

        return True, remaining, reset_time

    def cleanup_old_entries(self):
        """
        Cleanup old entries from memory

        Should be called periodically to prevent memory leaks
        In production with Redis, this is handled automatically by TTL
        """
        current_time = time.time()
        window_start = current_time - self.window_size

        for user_id in list(self.request_counts.keys()):
            user_requests = self.request_counts[user_id]
            user_requests = [req_time for req_time in user_requests if req_time > window_start]

            if user_requests:
                self.request_counts[user_id] = user_requests
            else:
                # Remove empty entries
                del self.request_counts[user_id]


# Production implementation with Redis:
#
# import redis
# from redis import Redis
#
# class RedisRateLimiter:
#     def __init__(self, redis_client: Redis, requests_per_minute: int = 30):
#         self.redis = redis_client
#         self.requests_per_minute = requests_per_minute
#         self.window_size = 60
#
#     def check_rate_limit(self, user_id: str) -> Tuple[bool, int, float]:
#         key = f"rate_limit:{user_id}"
#         current_time = time.time()
#         window_start = current_time - self.window_size
#
#         # Remove old requests
#         self.redis.zremrangebyscore(key, 0, window_start)
#
#         # Count requests in window
#         request_count = self.redis.zcard(key)
#
#         if request_count >= self.requests_per_minute:
#             # Get oldest request for reset time
#             oldest = self.redis.zrange(key, 0, 0, withscores=True)
#             if oldest:
#                 reset_time = oldest[0][1] + self.window_size
#             else:
#                 reset_time = current_time + self.window_size
#             return False, 0, reset_time
#
#         # Add current request
#         self.redis.zadd(key, {str(current_time): current_time})
#         self.redis.expire(key, self.window_size)
#
#         remaining = self.requests_per_minute - (request_count + 1)
#         reset_time = current_time + self.window_size
#
#         return True, remaining, reset_time
