# Omni — Subscription & Monetisation Architecture

## Executive Summary

Omni is a multi-device AI agent platform powered by Gemini Live. The primary recurring cost is **Vertex AI token consumption** (voice + text + image generation), with secondary costs from MCP tool calls (Brave, Maps, E2B sandbox). This document defines a **credit-based subscription model** with Stripe billing, free-tier onboarding credits, and per-user usage enforcement — designed for production deployment.

---

## 1. Subscription Tiers

### Tier Definitions

| | **Free** | **Pro** | **Ultra** |
|---|---|---|---|
| **Price** | $0 | $12/month | $29/month |
| **Credits** | 500 one-time | 10,000/month | Unlimited\* |
| **Voice Minutes** | ~15 min | ~5 hrs | Unlimited |
| **Text Turns** | ~250 | ~5,000 | Unlimited |
| **Image Generation** | 5/day | 50/day | 200/day |
| **Personas** | Assistant only | All 4 | All 4 + custom |
| **MCP Plugins** | 3 active | 10 active | Unlimited |
| **E2B Sandbox** | ✗ | 30 min/month | 120 min/month |
| **Concurrent Devices** | 1 | 3 | 10 |
| **Session History** | 7 days | 90 days | Unlimited |
| **Planned Tasks** | 3 active | 20 active | Unlimited |
| **Priority Queue** | ✗ | ✗ | ✓ (lower latency) |
| **Support** | Community | Email | Priority |

\*Ultra "unlimited" is soft-capped at 100,000 credits/month. Overages billed at $0.002/credit.

### Credit Cost Table

Every API interaction consumes credits. This normalises heterogeneous costs into a single currency.

| Action | Credits | Approx. Real Cost |
|---|---|---|
| 1K input tokens (text) | 1 | $0.00015 |
| 1K output tokens (text) | 4 | $0.0006 |
| 1 sec voice input | 2 | ~$0.0003 |
| 1 sec voice output | 3 | ~$0.0005 |
| 1 image generation | 30 | ~$0.005 |
| 1 MCP tool call | 2 | ~$0.0003 |
| 1 min E2B sandbox | 10 | ~$0.0015 |
| 1 Brave search query | 3 | ~$0.005 |
| 1 Google Maps call | 3 | ~$0.005 |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Dashboard / Clients               │
│  ┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────┐ │
│  │  Web   │  │Desktop │  │ Chrome  │  │  Mobile  │ │
│  └───┬────┘  └───┬────┘  └────┬────┘  └────┬─────┘ │
│      └───────────┴────────────┴─────────────┘       │
│                        │                             │
│              WebSocket / REST API                    │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                  Backend (FastAPI)                    │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Auth MW      │→ │ Subscription │→ │ Usage Gate │ │
│  │ (Firebase)   │  │ MW (new)     │  │ MW (new)   │ │
│  └──────────────┘  └──────┬───────┘  └─────┬──────┘ │
│                           │                │         │
│  ┌────────────────────────▼────────────────▼───────┐ │
│  │              Subscription Service                │ │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────────┐  │ │
│  │  │ Plan     │ │ Credit    │ │ Feature Gate   │  │ │
│  │  │ Resolver │ │ Tracker   │ │ Enforcer       │  │ │
│  │  └──────────┘ └───────────┘ └────────────────┘  │ │
│  └──────────────────────┬──────────────────────────┘ │
│                         │                            │
│  ┌──────────────────────▼──────────────────────────┐ │
│  │              Agent Pipeline (ADK)                │ │
│  │  before_model → model → after_model → tool_call │ │
│  │       ↑              ↑                    ↑      │ │
│  │  credit check   token count          credit dec  │ │
│  └──────────────────────────────────────────────────┘ │
│                         │                            │
└─────────────────────────┼────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
   ┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
   │  Firestore  │ │   Stripe   │ │  Vertex AI  │
   │ (sub state, │ │ (payments, │ │  (Gemini    │
   │  credits,   │ │  webhooks) │ │   Live)     │
   │  usage log) │ │            │ │             │
   └─────────────┘ └────────────┘ └─────────────┘
```

---

## 3. Firestore Data Model

### 3.1 `subscriptions/{user_id}`

Single document per user. Created on first login.

```json
{
  "user_id": "firebase_uid_abc",
  "plan": "free",                        // "free" | "pro" | "ultra"
  "status": "active",                    // "active" | "past_due" | "canceled" | "trialing"
  "stripe_customer_id": "cus_xxx",       // null for free users until they enter payment
  "stripe_subscription_id": "sub_xxx",   // null for free
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "cancel_at_period_end": false,
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-11T12:00:00Z"
}
```

### 3.2 `subscriptions/{user_id}/credits/current`

Rolling credit balance. Updated atomically on every API call via Firestore transactions.

```json
{
  "balance": 4200,                       // Remaining credits this period
  "lifetime_used": 128500,               // Total credits ever consumed
  "period_used": 5800,                   // Credits used this billing cycle
  "period_limit": 10000,                 // Plan cap (0 = unlimited*)
  "bonus_credits": 0,                    // Promotional / referral credits (never expire)
  "reset_at": "2026-05-01T00:00:00Z",   // When period_used resets
  "updated_at": "2026-04-11T12:15:00Z"
}
```

### 3.3 `subscriptions/{user_id}/usage_log/{auto_id}`

Append-only usage trail for audit, analytics, and billing disputes.

```json
{
  "action": "voice_output",              // "text_input" | "text_output" | "voice_input" | "voice_output" | "image_gen" | "mcp_call" | "sandbox_min"
  "credits": 45,
  "session_id": "sess_abc",
  "persona": "coder",
  "model": "gemini-live-2.5-flash-native-audio",
  "metadata": {
    "tokens_in": 0,
    "tokens_out": 0,
    "audio_seconds": 15
  },
  "timestamp": "2026-04-11T12:15:30Z"
}
```

### 3.4 `subscriptions/{user_id}/feature_flags`

Cached feature entitlements (denormalised from plan for fast reads).

```json
{
  "max_personas": 1,                     // free=1, pro=4, ultra=-1 (unlimited)
  "max_active_mcps": 3,                  // free=3, pro=10, ultra=-1
  "max_devices": 1,                      // free=1, pro=3, ultra=10
  "max_active_tasks": 3,                 // free=3, pro=20, ultra=-1
  "image_gen_daily_limit": 5,            // free=5, pro=50, ultra=200
  "sandbox_enabled": false,              // free=false, pro=true, ultra=true
  "sandbox_minutes_monthly": 0,          // free=0, pro=30, ultra=120
  "session_retention_days": 7,           // free=7, pro=90, ultra=-1
  "priority_queue": false,               // ultra only
  "custom_personas": false               // ultra only
}
```

---

## 4. Backend Implementation

### 4.1 Subscription Service — `backend/app/services/subscription_service.py`

```python
"""Subscription & credit management service.

Manages plan resolution, credit balance, usage tracking,
and feature entitlements backed by Firestore.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from google.cloud.firestore_v1 import AsyncClient, async_transactional

from app.services.firestore_client import get_firestore
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"
    ULTRA = "ultra"


class SubStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


# ── Plan Limits ──────────────────────────────────────────────────────

PLAN_CONFIG: dict[Plan, dict[str, Any]] = {
    Plan.FREE: {
        "credits_monthly": 500,            # one-time grant (doesn't reset)
        "credits_reset": False,            # free credits don't replenish
        "max_personas": 1,
        "max_active_mcps": 3,
        "max_devices": 1,
        "max_active_tasks": 3,
        "image_gen_daily_limit": 5,
        "sandbox_enabled": False,
        "sandbox_minutes_monthly": 0,
        "session_retention_days": 7,
        "priority_queue": False,
        "custom_personas": False,
    },
    Plan.PRO: {
        "credits_monthly": 10_000,
        "credits_reset": True,
        "max_personas": 4,
        "max_active_mcps": 10,
        "max_devices": 3,
        "max_active_tasks": 20,
        "image_gen_daily_limit": 50,
        "sandbox_enabled": True,
        "sandbox_minutes_monthly": 30,
        "session_retention_days": 90,
        "priority_queue": False,
        "custom_personas": False,
    },
    Plan.ULTRA: {
        "credits_monthly": 100_000,
        "credits_reset": True,
        "max_personas": -1,               # unlimited
        "max_active_mcps": -1,
        "max_devices": 10,
        "max_active_tasks": -1,
        "image_gen_daily_limit": 200,
        "sandbox_enabled": True,
        "sandbox_minutes_monthly": 120,
        "session_retention_days": -1,      # unlimited
        "priority_queue": True,
        "custom_personas": True,
    },
}


class SubscriptionService:
    """Firestore-backed subscription manager."""

    def __init__(self) -> None:
        self._db: AsyncClient | None = None

    @property
    def db(self) -> AsyncClient:
        if self._db is None:
            self._db = get_firestore()
        return self._db

    # ── Subscription CRUD ────────────────────────────────────────────

    async def get_or_create_subscription(self, user_id: str) -> dict:
        """Return the user's subscription doc, creating free tier if missing."""
        ref = self.db.collection("subscriptions").document(user_id)
        doc = await ref.get()
        if doc.exists:
            return doc.to_dict()

        # First-time user → free plan with starter credits
        now = datetime.now(timezone.utc).isoformat()
        sub = {
            "user_id": user_id,
            "plan": Plan.FREE.value,
            "status": SubStatus.ACTIVE.value,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "current_period_start": now,
            "current_period_end": None,       # Free tier has no period
            "cancel_at_period_end": False,
            "created_at": now,
            "updated_at": now,
        }
        await ref.set(sub)

        # Grant one-time starter credits
        await self._init_credits(user_id, Plan.FREE)
        # Cache feature flags
        await self._sync_feature_flags(user_id, Plan.FREE)
        logger.info("subscription_created", user_id=user_id, plan="free")
        return sub

    async def update_plan(self, user_id: str, plan: Plan, stripe_sub_id: str | None = None) -> dict:
        """Upgrade/downgrade a user's plan. Called from Stripe webhook handler."""
        ref = self.db.collection("subscriptions").document(user_id)
        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "plan": plan.value,
            "status": SubStatus.ACTIVE.value,
            "stripe_subscription_id": stripe_sub_id,
            "updated_at": now,
        }
        await ref.update(updates)
        await self._reset_credits(user_id, plan)
        await self._sync_feature_flags(user_id, plan)
        logger.info("subscription_updated", user_id=user_id, plan=plan.value)
        return {**updates}

    # ── Credit Management ────────────────────────────────────────────

    async def _init_credits(self, user_id: str, plan: Plan) -> None:
        """Initialise credit doc for a new user."""
        config = PLAN_CONFIG[plan]
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        await ref.set({
            "balance": config["credits_monthly"],
            "lifetime_used": 0,
            "period_used": 0,
            "period_limit": config["credits_monthly"],
            "bonus_credits": 0,
            "reset_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    async def _reset_credits(self, user_id: str, plan: Plan) -> None:
        """Reset credits for a new billing period or plan change."""
        config = PLAN_CONFIG[plan]
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        doc = await ref.get()
        existing = doc.to_dict() if doc.exists else {}
        await ref.set({
            "balance": config["credits_monthly"],
            "lifetime_used": existing.get("lifetime_used", 0),
            "period_used": 0,
            "period_limit": config["credits_monthly"],
            "bonus_credits": existing.get("bonus_credits", 0),
            "reset_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    async def get_credit_balance(self, user_id: str) -> dict:
        """Return the current credit state."""
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        doc = await ref.get()
        return doc.to_dict() if doc.exists else {"balance": 0}

    async def deduct_credits(self, user_id: str, amount: int, action: str,
                             session_id: str = "", metadata: dict | None = None) -> bool:
        """Atomically deduct credits. Returns False if insufficient balance."""
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("credits")
            .document("current")
        )

        @async_transactional
        async def _txn(txn):
            doc = await ref.get(transaction=txn)
            if not doc.exists:
                return False
            data = doc.to_dict()
            effective_balance = data.get("balance", 0) + data.get("bonus_credits", 0)
            if effective_balance < amount:
                return False

            # Deduct from bonus first, then regular balance
            bonus = data.get("bonus_credits", 0)
            if bonus >= amount:
                txn.update(ref, {
                    "bonus_credits": bonus - amount,
                    "lifetime_used": data.get("lifetime_used", 0) + amount,
                    "period_used": data.get("period_used", 0) + amount,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
            else:
                remaining = amount - bonus
                txn.update(ref, {
                    "bonus_credits": 0,
                    "balance": data.get("balance", 0) - remaining,
                    "lifetime_used": data.get("lifetime_used", 0) + amount,
                    "period_used": data.get("period_used", 0) + amount,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
            return True

        txn = self.db.transaction()
        success = await _txn(txn)

        if success:
            # Append usage log (fire-and-forget)
            asyncio.create_task(self._log_usage(user_id, action, amount, session_id, metadata))
        else:
            logger.warning("credits_insufficient", user_id=user_id, action=action, amount=amount)

        return success

    async def _log_usage(self, user_id: str, action: str, credits: int,
                         session_id: str, metadata: dict | None) -> None:
        """Append to the usage log subcollection."""
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("usage_log")
        )
        await ref.add({
            "action": action,
            "credits": credits,
            "session_id": session_id,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Feature Flags ────────────────────────────────────────────────

    async def _sync_feature_flags(self, user_id: str, plan: Plan) -> None:
        """Write denormalised feature flags from plan config."""
        config = PLAN_CONFIG[plan]
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("feature_flags")
            .document("current")          # single doc, not a collection
        )
        flags = {k: v for k, v in config.items() if k not in ("credits_monthly", "credits_reset")}
        await ref.set(flags)

    async def get_feature_flags(self, user_id: str) -> dict:
        """Return cached feature entitlements."""
        ref = (
            self.db.collection("subscriptions")
            .document(user_id)
            .collection("feature_flags")
            .document("current")
        )
        doc = await ref.get()
        if doc.exists:
            return doc.to_dict()
        # Fallback to free defaults
        return {k: v for k, v in PLAN_CONFIG[Plan.FREE].items()
                if k not in ("credits_monthly", "credits_reset")}

    async def check_feature(self, user_id: str, feature: str, current_count: int = 0) -> bool:
        """Check if user is within their plan's limit for a feature.
        
        Returns True if allowed, False if at/over limit.
        -1 in the flags means unlimited.
        """
        flags = await self.get_feature_flags(user_id)
        limit = flags.get(feature, 0)
        if limit == -1:
            return True
        return current_count < limit


# Module-level singleton
_service: SubscriptionService | None = None

def get_subscription_service() -> SubscriptionService:
    global _service
    if _service is None:
        _service = SubscriptionService()
    return _service
```

### 4.2 Subscription Middleware — `backend/app/middleware/subscription_middleware.py`

```python
"""Middleware that attaches subscription context to every authenticated request.

Runs AFTER auth middleware. Injects `request.state.subscription` and
`request.state.feature_flags` for downstream handlers to use.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.services.subscription_service import get_subscription_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SubscriptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip unauthenticated routes
        if not hasattr(request.state, "user"):
            return await call_next(request)

        user_id = request.state.user.uid
        svc = get_subscription_service()

        # Lazy-initialise subscription on first request
        sub = await svc.get_or_create_subscription(user_id)
        credits = await svc.get_credit_balance(user_id)
        flags = await svc.get_feature_flags(user_id)

        request.state.subscription = sub
        request.state.credits = credits
        request.state.feature_flags = flags

        response = await call_next(request)

        # Attach credit info in response headers
        response.headers["X-Credits-Remaining"] = str(credits.get("balance", 0))
        response.headers["X-Plan"] = sub.get("plan", "free")
        return response
```

### 4.3 Usage Gate Middleware — `backend/app/middleware/usage_gate.py`

```python
"""Blocks requests when credits are exhausted.

Returns HTTP 402 Payment Required with upgrade prompt.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Paths that should never be blocked (billing pages, auth, health)
_EXEMPT_PATHS = {"/health", "/auth/verify", "/auth/me", "/api/subscription", "/api/billing"}


class UsageGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip exempt paths and unauthenticated requests
        if path in _EXEMPT_PATHS or path.startswith("/api/billing"):
            return await call_next(request)
        if not hasattr(request.state, "credits"):
            return await call_next(request)

        credits = request.state.credits
        balance = credits.get("balance", 0) + credits.get("bonus_credits", 0)

        if balance <= 0:
            plan = getattr(request.state, "subscription", {}).get("plan", "free")
            logger.warning("credits_exhausted", user_id=request.state.user.uid, plan=plan)
            return JSONResponse(
                status_code=402,
                content={
                    "error": "credits_exhausted",
                    "message": "You've used all your credits.",
                    "plan": plan,
                    "upgrade_url": "/settings/billing",
                },
            )

        return await call_next(request)
```

### 4.4 Credit Deduction in ADK Callbacks — `backend/app/middleware/agent_callbacks.py`

Integration point: hook into the existing `cost_estimation_callback` to deduct credits after each model response.

```python
# Add to the existing cost_estimation_callback in agent_callbacks.py:

async def deduct_credits_from_usage(user_id: str, session_id: str,
                                     input_tokens: int, output_tokens: int) -> bool:
    """Convert token counts to credits and deduct."""
    from app.services.subscription_service import get_subscription_service

    svc = get_subscription_service()

    # Calculate credits: 1 credit per 1K input tokens, 4 credits per 1K output tokens
    input_credits = max(1, input_tokens // 1000)
    output_credits = max(1, (output_tokens * 4) // 1000)
    total = input_credits + output_credits

    return await svc.deduct_credits(
        user_id=user_id,
        amount=total,
        action="model_inference",
        session_id=session_id,
        metadata={"tokens_in": input_tokens, "tokens_out": output_tokens},
    )
```

### 4.5 WebSocket Credit Check — `backend/app/api/ws_live.py`

For voice sessions, check credits before establishing the live connection and periodically during streaming.

```python
# At the start of websocket_live(), after auth:

sub_svc = get_subscription_service()
credits = await sub_svc.get_credit_balance(user.uid)
if (credits.get("balance", 0) + credits.get("bonus_credits", 0)) <= 0:
    err = ErrorMessage(
        code="credits_exhausted",
        description="You've used all your credits. Upgrade your plan to continue.",
    )
    await websocket.send_text(err.model_dump_json())
    await websocket.close(code=4402, reason="credits_exhausted")
    return

# During _consume_downstream(), deduct credits per audio chunk:
# Every 10 seconds of streamed audio → deduct 30 credits (10s × 3 credits/sec)
```

### 4.6 Stripe Integration — `backend/app/api/billing.py`

```python
"""Stripe billing API routes.

Handles checkout sessions, portal links, and webhook events.
"""

import stripe
from fastapi import APIRouter, Depends, Header, Request
from starlette.responses import JSONResponse

from app.config import settings
from app.middleware.auth_middleware import CurrentUser
from app.services.subscription_service import Plan, get_subscription_service
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = get_logger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

# Map Stripe price IDs to plans
PRICE_TO_PLAN = {
    settings.STRIPE_PRO_PRICE_ID: Plan.PRO,
    settings.STRIPE_ULTRA_PRICE_ID: Plan.ULTRA,
}


@router.post("/checkout")
async def create_checkout_session(plan: str, user: CurrentUser):
    """Create a Stripe Checkout session for upgrade."""
    price_id = {
        "pro": settings.STRIPE_PRO_PRICE_ID,
        "ultra": settings.STRIPE_ULTRA_PRICE_ID,
    }.get(plan)

    if not price_id:
        return JSONResponse(status_code=400, content={"error": "Invalid plan"})

    svc = get_subscription_service()
    sub = await svc.get_or_create_subscription(user.uid)

    # Create or reuse Stripe customer
    if not sub.get("stripe_customer_id"):
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"firebase_uid": user.uid},
        )
        customer_id = customer.id
        # Store customer ID
        from app.services.firestore_client import get_firestore
        db = get_firestore()
        await db.collection("subscriptions").document(user.uid).update({
            "stripe_customer_id": customer_id,
        })
    else:
        customer_id = sub["stripe_customer_id"]

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.FRONTEND_URL}/settings/billing?success=true",
        cancel_url=f"{settings.FRONTEND_URL}/settings/billing?canceled=true",
        metadata={"firebase_uid": user.uid, "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal_session(user: CurrentUser):
    """Create a Stripe Customer Portal session for plan management."""
    svc = get_subscription_service()
    sub = await svc.get_or_create_subscription(user.uid)

    if not sub.get("stripe_customer_id"):
        return JSONResponse(status_code=400, content={"error": "No active subscription"})

    session = stripe.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url=f"{settings.FRONTEND_URL}/settings/billing",
    )
    return {"portal_url": session.url}


@router.get("/status")
async def get_billing_status(user: CurrentUser):
    """Return current subscription status + credit balance."""
    svc = get_subscription_service()
    sub = await svc.get_or_create_subscription(user.uid)
    credits = await svc.get_credit_balance(user.uid)
    flags = await svc.get_feature_flags(user.uid)

    return {
        "plan": sub.get("plan"),
        "status": sub.get("status"),
        "credits": credits,
        "features": flags,
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
    }


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(alias="Stripe-Signature")):
    """Handle Stripe webhook events.
    
    CRITICAL: Verify webhook signature to prevent spoofing.
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning("stripe_webhook_invalid_signature")
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    svc = get_subscription_service()

    match event["type"]:

        case "checkout.session.completed":
            session = event["data"]["object"]
            uid = session["metadata"]["firebase_uid"]
            plan_name = session["metadata"]["plan"]
            stripe_sub_id = session.get("subscription")
            plan = Plan(plan_name)
            await svc.update_plan(uid, plan, stripe_sub_id)
            logger.info("stripe_checkout_completed", user_id=uid, plan=plan_name)

        case "customer.subscription.updated":
            sub_obj = event["data"]["object"]
            customer_id = sub_obj["customer"]
            # Look up user by stripe_customer_id
            uid = await _resolve_uid(customer_id)
            if uid:
                price_id = sub_obj["items"]["data"][0]["price"]["id"]
                plan = PRICE_TO_PLAN.get(price_id, Plan.FREE)
                cancel_at_end = sub_obj.get("cancel_at_period_end", False)
                await svc.update_plan(uid, plan, sub_obj["id"])
                if cancel_at_end:
                    from app.services.firestore_client import get_firestore
                    db = get_firestore()
                    await db.collection("subscriptions").document(uid).update({
                        "cancel_at_period_end": True,
                    })

        case "customer.subscription.deleted":
            sub_obj = event["data"]["object"]
            customer_id = sub_obj["customer"]
            uid = await _resolve_uid(customer_id)
            if uid:
                await svc.update_plan(uid, Plan.FREE)
                logger.info("stripe_subscription_canceled", user_id=uid)

        case "invoice.payment_failed":
            sub_obj = event["data"]["object"]
            customer_id = sub_obj["customer"]
            uid = await _resolve_uid(customer_id)
            if uid:
                from app.services.firestore_client import get_firestore
                db = get_firestore()
                await db.collection("subscriptions").document(uid).update({
                    "status": "past_due",
                })
                logger.warning("stripe_payment_failed", user_id=uid)

    return {"received": True}


async def _resolve_uid(stripe_customer_id: str) -> str | None:
    """Find Firebase UID from Stripe customer ID."""
    from app.services.firestore_client import get_firestore
    db = get_firestore()
    docs = db.collection("subscriptions").where("stripe_customer_id", "==", stripe_customer_id).limit(1)
    async for doc in docs.stream():
        return doc.to_dict().get("user_id")
    return None
```

### 4.7 Config Additions — `backend/app/config.py`

```python
# Add to Settings class:

# ── Stripe Billing ───────────────────────────────────────────────
STRIPE_SECRET_KEY: str = ""               # sk_live_...
STRIPE_WEBHOOK_SECRET: str = ""           # whsec_...
STRIPE_PRO_PRICE_ID: str = ""             # price_...
STRIPE_ULTRA_PRICE_ID: str = ""           # price_...
FRONTEND_URL: str = "https://omni.app"    # For Stripe redirect URLs
```

---

## 5. Middleware Registration Order

In `backend/app/main.py`, middleware executes in **reverse registration order** (last registered = first executed):

```python
# Register in this order (bottom runs first):
app.add_middleware(UsageGateMiddleware)          # 3rd: block if no credits
app.add_middleware(SubscriptionMiddleware)       # 2nd: attach plan + credits
# Auth middleware is already registered          # 1st: verify Firebase JWT
```

Request flow: **Auth → Subscription → UsageGate → Route Handler**

---

## 6. Feature Gating Implementation

### 6.1 MCP Plugin Limit

In `backend/app/api/plugins.py`, check active MCP count before enabling:

```python
@router.post("/plugins/toggle")
async def toggle_plugin(plugin_id: str, enabled: bool, user: CurrentUser):
    svc = get_subscription_service()
    if enabled:
        active_count = await get_active_plugin_count(user.uid)
        allowed = await svc.check_feature(user.uid, "max_active_mcps", active_count)
        if not allowed:
            return JSONResponse(status_code=403, content={
                "error": "plan_limit",
                "message": "Upgrade your plan to enable more plugins.",
                "feature": "max_active_mcps",
            })
    # ... existing toggle logic
```

### 6.2 Concurrent Device Limit

In `backend/app/api/ws_live.py`, check connected device count:

```python
# At connection time, before accepting WebSocket:
device_count = connection_manager.get_user_connection_count(user.uid)
flags = await sub_svc.get_feature_flags(user.uid)
max_devices = flags.get("max_devices", 1)
if max_devices != -1 and device_count >= max_devices:
    err = ErrorMessage(
        code="device_limit",
        description=f"Your plan allows {max_devices} device(s). Disconnect another device or upgrade.",
    )
    await websocket.send_text(err.model_dump_json())
    await websocket.close(code=4403)
    return
```

### 6.3 Persona Access

In persona switching logic:

```python
allowed_personas = flags.get("max_personas", 1)
if allowed_personas != -1:
    # Free tier: only "assistant" persona
    if persona_id != "assistant":
        # Block switch, send upgrade prompt
```

### 6.4 Image Generation Daily Limit

```python
# Before calling image_gen tool:
today_count = await get_daily_image_count(user_id)
daily_limit = flags.get("image_gen_daily_limit", 5)
if today_count >= daily_limit:
    return {"error": f"Daily image limit reached ({daily_limit}). Resets at midnight UTC."}
```

---

## 7. Free Tier Onboarding Flow

```
User signs up (Firebase Auth)
        │
        ▼
First API request hits SubscriptionMiddleware
        │
        ▼
get_or_create_subscription() → creates Free plan doc
        │
        ▼
_init_credits() → grants 500 one-time credits
        │
        ▼
_sync_feature_flags() → writes Free tier limits
        │
        ▼
User gets ~15 min voice / ~250 text turns to explore
        │
        ▼
Credits approach 0 → dashboard shows warning banner
        │
        ▼
Credits hit 0 → 402 response + upgrade modal
        │
        ▼
User clicks upgrade → Stripe Checkout → Pro/Ultra
        │
        ▼
Webhook fires → update_plan() → credits reset + flags updated
```

### Referral / Bonus Credits

```python
# Award bonus credits (never expire, used before plan credits)
async def grant_bonus_credits(user_id: str, amount: int, reason: str):
    ref = db.collection("subscriptions").document(user_id).collection("credits").document("current")
    doc = await ref.get()
    current_bonus = doc.to_dict().get("bonus_credits", 0)
    await ref.update({"bonus_credits": current_bonus + amount})
    logger.info("bonus_credits_granted", user_id=user_id, amount=amount, reason=reason)
```

| Trigger | Bonus Credits |
|---|---|
| Sign up | 500 (one-time, via plan) |
| Referred a friend | +200 |
| Friend upgrades to Pro | +500 |
| Feedback survey | +100 |
| Bug report accepted | +300 |

---

## 8. Dashboard UI Integration

### 8.1 Billing Settings Page — `dashboard/src/pages/BillingPage.jsx`

New tab in SettingsPage or standalone page:

```
┌─────────────────────────────────────────────────────┐
│  Settings > Billing                                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Current Plan: PRO                    [Manage Plan]  │
│  Status: Active                                      │
│  Next billing: May 1, 2026                          │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │  Credits This Month                          │    │
│  │  ████████████████████░░░░░  6,200 / 10,000   │    │
│  │  38% remaining · Resets May 1                │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  Usage Breakdown (this period)                       │
│  ┌──────────────┬──────────┬────────┐               │
│  │ Voice I/O    │  3,200   │  52%   │               │
│  │ Text turns   │  1,800   │  29%   │               │
│  │ Image gen    │    600   │  10%   │               │
│  │ MCP calls    │    400   │   6%   │               │
│  │ Sandbox      │    200   │   3%   │               │
│  └──────────────┴──────────┴────────┘               │
│                                                      │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐            │
│  │  FREE   │  │   PRO   │  │  ULTRA   │            │
│  │  $0/mo  │  │ $12/mo  │  │  $29/mo  │            │
│  │ 500 cr  │  │ 10k cr  │  │ 100k cr  │            │
│  │         │  │ ✓ curr  │  │[Upgrade] │            │
│  └─────────┘  └─────────┘  └──────────┘            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 8.2 Credit Warning Banner

Shows globally when credits < 20% remaining:

```jsx
// In App.jsx or layout component:
{credits.balance < credits.period_limit * 0.2 && (
  <Banner variant="warning">
    ⚡ {credits.balance} credits left · <Link to="/settings/billing">Upgrade</Link>
  </Banner>
)}
```

### 8.3 Exhaustion Modal

Full-screen overlay when credits = 0:

```jsx
{credits.balance <= 0 && (
  <Modal title="Credits exhausted" closeable={false}>
    <p>Upgrade to continue using Omni.</p>
    <PlanSelector onSelect={handleUpgrade} />
  </Modal>
)}
```

---

## 9. Stripe Setup Checklist

### Stripe Dashboard Configuration

1. Create Products:
   - **Omni Pro** → Recurring $12/month → note `price_id`
   - **Omni Ultra** → Recurring $29/month → note `price_id`

2. Configure Customer Portal:
   - Enable plan switching (Pro ↔ Ultra)
   - Enable cancellation with feedback survey
   - Enable invoice history

3. Webhook Endpoints:
   - URL: `https://api.omni.app/api/billing/webhook`
   - Events to listen for:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_failed`

4. Environment Variables:
   ```yaml
   STRIPE_SECRET_KEY: sk_live_...
   STRIPE_WEBHOOK_SECRET: whsec_...
   STRIPE_PRO_PRICE_ID: price_...
   STRIPE_ULTRA_PRICE_ID: price_...
   ```

---

## 10. Credit Reset — Cloud Scheduler Job

For Pro/Ultra users, credits reset monthly. Use Cloud Scheduler + Cloud Functions:

```python
# Scheduled function — runs daily at 00:05 UTC
async def reset_expired_credits():
    """Reset credits for users whose billing period has ended."""
    db = get_firestore()
    now = datetime.now(timezone.utc)

    # Query subscriptions where current_period_end < now
    query = (
        db.collection("subscriptions")
        .where("status", "==", "active")
        .where("plan", "in", ["pro", "ultra"])
        .where("current_period_end", "<=", now.isoformat())
    )

    async for doc in query.stream():
        data = doc.to_dict()
        user_id = data["user_id"]
        plan = Plan(data["plan"])
        svc = get_subscription_service()
        await svc._reset_credits(user_id, plan)
        # Update period timestamps from Stripe
        logger.info("credits_reset", user_id=user_id, plan=plan.value)
```

---

## 11. Firestore Indexes

Add to `firestore.indexes.json`:

```json
{
  "indexes": [
    {
      "collectionGroup": "subscriptions",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "plan", "order": "ASCENDING" },
        { "fieldPath": "current_period_end", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "usage_log",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "action", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    }
  ]
}
```

---

## 12. Security Considerations

| Concern | Mitigation |
|---|---|
| Stripe webhook spoofing | Signature verification via `stripe.Webhook.construct_event()` |
| Credit manipulation | Firestore transactions for atomic deductions (no race conditions) |
| Plan self-assignment | Plan changes ONLY via Stripe webhooks, never client-facing API |
| Usage log tampering | Usage log is append-only, no client write access |
| Feature flag bypass | Flags checked server-side in middleware + route handlers |
| Credit overflow | `bonus_credits` capped; plan credits bounded by `period_limit` |
| Firestore rules | Subscription docs writable only by service account (admin SDK) |

---

## 13. Implementation Priority

| Phase | Scope | Effort |
|---|---|---|
| **Phase 1** | Firestore subscription model + free tier auto-creation + credit tracking | 3–4 days |
| **Phase 2** | Stripe integration (checkout, webhooks, portal) + billing API | 2–3 days |
| **Phase 3** | Feature gating (MCP limits, personas, devices) | 2 days |
| **Phase 4** | Dashboard billing page + credit bar + exhaustion modal | 2–3 days |
| **Phase 5** | Usage analytics page + credit reset scheduler | 1–2 days |
| **Phase 6** | Referral system + bonus credits | 1 day |
