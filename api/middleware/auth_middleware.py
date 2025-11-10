"""Authentication middleware for extracting user info from JWT"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from auth_utils import decode_access_token

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract user information from JWT token

    This middleware runs before other middleware and extracts user_id
    from the Authorization header if present. The user_id is stored
    in request.state for use by other middleware (e.g., rate limiting).

    Note: This middleware does NOT enforce authentication.
    Use auth dependencies in routes for that purpose.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Extract user_id from Authorization header and store in request.state

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            # Decode token
            payload = decode_access_token(token)

            if payload:
                user_id_str = payload.get("sub")
                if user_id_str:
                    # Store user_id in request state for other middleware
                    request.state.user_id = user_id_str
                    logger.debug(f"User {user_id_str} authenticated via middleware")

        # Continue to next middleware/handler
        return await call_next(request)
