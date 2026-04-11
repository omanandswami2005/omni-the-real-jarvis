"""Subscription context middleware.

Runs AFTER auth middleware. Attaches ``request.state.subscription``,
``request.state.credits``, and ``request.state.feature_flags`` so
downstream handlers and the usage gate can inspect them.
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.services.subscription_service import get_subscription_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SubscriptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only applies to authenticated requests
        if not hasattr(request.state, "user"):
            return await call_next(request)

        user_id = request.state.user.uid
        svc = get_subscription_service()

        try:
            sub = await svc.get_or_create_subscription(user_id)
            credits = await svc.get_credit_balance(user_id)
            effective_plan = svc.resolve_effective_plan(user_id, sub.get("plan"))
            flags = svc.get_feature_flags(user_id, effective_plan)
        except Exception:
            # If Firestore is down, don't block the request — assume free tier
            logger.warning("subscription_middleware_error", user_id=user_id, exc_info=True)
            sub = {"plan": "free", "status": "active"}
            credits = {"balance": 500, "period_limit": 500}
            flags = {}

        request.state.subscription = sub
        request.state.credits = credits
        request.state.feature_flags = flags

        response = await call_next(request)

        # Informational headers
        response.headers["X-Credits-Remaining"] = str(credits.get("balance", 0))
        response.headers["X-Plan"] = sub.get("plan", "free")
        return response
