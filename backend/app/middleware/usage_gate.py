"""Usage gate middleware — blocks requests when credits are exhausted.

Returns HTTP 402 Payment Required with upgrade info.
Admin/tester UIDs are never blocked.
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Paths that must always be accessible (billing, auth, health)
_EXEMPT_PREFIXES = (
    "/health",
    "/api/v1/health",
    "/api/v1/auth",
    "/api/v1/billing",
    "/ws/",               # WebSocket has its own credit check at connect time
    "/docs",
    "/redoc",
    "/openapi.json",
)


class UsageGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip exempt paths
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip unauthenticated (auth middleware will reject anyway)
        if not hasattr(request.state, "credits"):
            return await call_next(request)

        credits = request.state.credits

        # Override users are never blocked
        if credits.get("unlimited"):
            return await call_next(request)

        balance = credits.get("balance", 0) + credits.get("bonus_credits", 0)

        if balance <= 0:
            plan = getattr(request.state, "subscription", {}).get("plan", "free")
            user_id = request.state.user.uid if hasattr(request.state, "user") else "?"
            logger.warning("credits_exhausted_blocked", user_id=user_id, plan=plan, path=path)
            return JSONResponse(
                status_code=402,
                content={
                    "error": "credits_exhausted",
                    "message": "You've used all your credits. Upgrade your plan to continue.",
                    "plan": plan,
                    "upgrade_url": "/settings?tab=Billing",
                },
            )

        return await call_next(request)
