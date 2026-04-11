"""Billing API — Stripe checkout, portal, webhook, subscription status,
and admin credit management endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from starlette.responses import JSONResponse

from app.config import settings
from app.middleware.auth_middleware import CurrentUser
from app.services.subscription_service import (
    CREDIT_COSTS,
    PLAN_CONFIG,
    Plan,
    get_subscription_service,
)
from app.utils.logging import get_logger

router = APIRouter(tags=["billing"])
logger = get_logger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────

def _get_stripe():
    """Lazy-import stripe so the app boots even without the key."""
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


PRICE_TO_PLAN: dict[str, Plan] = {}   # populated at first call


def _ensure_price_map():
    if PRICE_TO_PLAN:
        return
    if settings.STRIPE_PRO_PRICE_ID:
        PRICE_TO_PLAN[settings.STRIPE_PRO_PRICE_ID] = Plan.PRO
    if settings.STRIPE_ULTRA_PRICE_ID:
        PRICE_TO_PLAN[settings.STRIPE_ULTRA_PRICE_ID] = Plan.ULTRA


# ── Public routes (authenticated) ────────────────────────────────────

@router.get("/billing/status")
async def billing_status(user: CurrentUser):
    """Return current plan, credits, and feature flags."""
    svc = get_subscription_service()
    sub = await svc.get_or_create_subscription(user.uid)
    credits = await svc.get_credit_balance(user.uid)
    effective_plan = svc.resolve_effective_plan(user.uid, sub.get("plan"))
    flags = svc.get_feature_flags(user.uid, effective_plan)

    return {
        "plan": effective_plan.value,
        "status": sub.get("status", "active"),
        "credits": credits,
        "features": flags,
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "is_override": svc.is_override_user(user.uid),
        "credit_costs": CREDIT_COSTS,
        "plans": {
            p.value: {
                "credits_monthly": c["credits_monthly"],
                "max_personas": c["max_personas"],
                "max_active_mcps": c["max_active_mcps"],
                "max_devices": c["max_devices"],
                "sandbox_enabled": c["sandbox_enabled"],
                "image_gen_daily_limit": c["image_gen_daily_limit"],
            }
            for p, c in PLAN_CONFIG.items()
            if p in (Plan.FREE, Plan.PRO, Plan.ULTRA)
        },
    }


@router.get("/billing/usage")
async def billing_usage(user: CurrentUser):
    """Return recent usage log."""
    svc = get_subscription_service()
    entries = await svc.get_usage_summary(user.uid, limit=200)
    return {"usage": entries}


@router.post("/billing/checkout")
async def create_checkout(user: CurrentUser, plan: str = "pro"):
    """Create a Stripe Checkout session for plan upgrade."""
    stripe = _get_stripe()
    if not settings.STRIPE_SECRET_KEY:
        return JSONResponse(status_code=503, content={"error": "Billing not configured"})

    price_id = {
        "pro": settings.STRIPE_PRO_PRICE_ID,
        "ultra": settings.STRIPE_ULTRA_PRICE_ID,
    }.get(plan)
    if not price_id:
        return JSONResponse(status_code=400, content={"error": "Invalid plan"})

    svc = get_subscription_service()
    sub = await svc.get_or_create_subscription(user.uid)

    # Create or reuse Stripe customer
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"firebase_uid": user.uid},
        )
        customer_id = customer.id
        import asyncio
        from google.cloud import firestore as _fs
        db = _fs.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        await asyncio.to_thread(
            db.collection("subscriptions").document(user.uid).update,
            {"stripe_customer_id": customer_id},
        )

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.FRONTEND_URL}/settings?tab=Billing&success=true",
        cancel_url=f"{settings.FRONTEND_URL}/settings?tab=Billing&canceled=true",
        metadata={"firebase_uid": user.uid, "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/billing/portal")
async def create_portal(user: CurrentUser):
    """Create a Stripe Customer Portal session for self-serve management."""
    stripe = _get_stripe()
    if not settings.STRIPE_SECRET_KEY:
        return JSONResponse(status_code=503, content={"error": "Billing not configured"})

    svc = get_subscription_service()
    sub = await svc.get_or_create_subscription(user.uid)

    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        return JSONResponse(status_code=400, content={"error": "No active billing account"})

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings?tab=Billing",
    )
    return {"portal_url": session.url}


# ── Stripe webhook (unauthenticated — signature-verified) ────────────

@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events. Signature-verified."""
    stripe = _get_stripe()
    if not settings.STRIPE_WEBHOOK_SECRET:
        return JSONResponse(status_code=503, content={"error": "Webhook not configured"})

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning("stripe_webhook_invalid_signature")
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    _ensure_price_map()
    svc = get_subscription_service()
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        uid = obj.get("metadata", {}).get("firebase_uid")
        plan_name = obj.get("metadata", {}).get("plan")
        stripe_sub_id = obj.get("subscription")
        if uid and plan_name:
            plan = Plan(plan_name)
            await svc.update_plan(uid, plan, stripe_sub_id)
            logger.info("stripe_checkout_completed", user_id=uid, plan=plan_name)

    elif event_type == "customer.subscription.updated":
        customer_id = obj.get("customer")
        uid = await _resolve_uid(customer_id)
        if uid:
            price_id = obj["items"]["data"][0]["price"]["id"]
            plan = PRICE_TO_PLAN.get(price_id, Plan.FREE)
            cancel_at_end = obj.get("cancel_at_period_end", False)
            await svc.update_plan(uid, plan, obj["id"])
            if cancel_at_end:
                import asyncio
                from google.cloud import firestore as _fs
                db = _fs.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
                await asyncio.to_thread(
                    db.collection("subscriptions").document(uid).update,
                    {"cancel_at_period_end": True},
                )

    elif event_type == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        uid = await _resolve_uid(customer_id)
        if uid:
            await svc.update_plan(uid, Plan.FREE)
            logger.info("stripe_subscription_canceled", user_id=uid)

    elif event_type == "invoice.payment_failed":
        customer_id = obj.get("customer")
        uid = await _resolve_uid(customer_id)
        if uid:
            import asyncio
            from google.cloud import firestore as _fs
            db = _fs.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
            await asyncio.to_thread(
                db.collection("subscriptions").document(uid).update,
                {"status": "past_due"},
            )
            logger.warning("stripe_payment_failed", user_id=uid)

    return {"received": True}


async def _resolve_uid(stripe_customer_id: str) -> str | None:
    """Lookup Firebase UID from Stripe customer ID in Firestore."""
    if not stripe_customer_id:
        return None
    import asyncio
    from google.cloud import firestore as _fs
    db = _fs.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
    query = (
        db.collection("subscriptions")
        .where("stripe_customer_id", "==", stripe_customer_id)
        .limit(1)
    )
    snaps = await asyncio.to_thread(lambda: list(query.stream()))
    for snap in snaps:
        return snap.to_dict().get("user_id")
    return None


# ── Admin endpoints (requires admin UID) ─────────────────────────────

def _require_admin(user: CurrentUser) -> None:
    """Raise 403 if user is not in ADMIN_UIDS."""
    from app.utils.errors import AuthorizationError
    if user.uid not in settings.admin_uid_set:
        raise AuthorizationError("Admin access required")


@router.post("/billing/admin/grant-credits")
async def admin_grant_credits(user: CurrentUser, target_uid: str = "",
                               amount: int = 0, reason: str = ""):
    """Grant bonus credits to any user (admin only)."""
    _require_admin(user)
    if not target_uid or amount <= 0:
        return JSONResponse(status_code=400, content={"error": "target_uid and amount > 0 required"})

    svc = get_subscription_service()
    await svc.grant_bonus_credits(target_uid, amount, reason)
    return {"granted": amount, "target_uid": target_uid, "reason": reason}


@router.post("/billing/admin/set-credits")
async def admin_set_credits(user: CurrentUser, target_uid: str = "", balance: int = 0):
    """Manually set a user's credit balance (admin only)."""
    _require_admin(user)
    if not target_uid:
        return JSONResponse(status_code=400, content={"error": "target_uid required"})

    svc = get_subscription_service()
    await svc.set_override_credits(target_uid, balance)
    return {"set_balance": balance, "target_uid": target_uid}


@router.post("/billing/admin/set-plan")
async def admin_set_plan(user: CurrentUser, target_uid: str = "", plan: str = "free"):
    """Force-set a user's plan (admin only). Useful for granting Pro/Ultra without Stripe."""
    _require_admin(user)
    if not target_uid or plan not in ("free", "pro", "ultra"):
        return JSONResponse(status_code=400, content={"error": "target_uid and valid plan required"})

    svc = get_subscription_service()
    await svc.update_plan(target_uid, Plan(plan))
    return {"plan": plan, "target_uid": target_uid}
