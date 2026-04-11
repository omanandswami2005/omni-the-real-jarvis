"""Subscription & credit management service.

Manages plan resolution, credit balance, usage tracking, feature
entitlements, and admin/tester overrides — backed by Firestore.

Firestore layout:
  subscriptions/{user_id}                → plan, status, stripe IDs
  subscriptions/{user_id}/credits/current → balance, period_used, …
  subscriptions/{user_id}/usage_log/{id}  → append-only audit trail
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from google.cloud import firestore

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

COLLECTION = "subscriptions"


# ── Plan / Status enums ──────────────────────────────────────────────

class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"
    ULTRA = "ultra"
    ADMIN = "admin"      # virtual plan for admin UIDs
    TESTER = "tester"    # virtual plan for tester UIDs


class SubStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


# ── Plan configuration ───────────────────────────────────────────────

PLAN_CONFIG: dict[Plan, dict[str, Any]] = {
    Plan.FREE: {
        "credits_monthly": 500,
        "credits_reset": False,          # one-time grant, no monthly reset
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
        "max_personas": -1,
        "max_active_mcps": -1,
        "max_devices": 10,
        "max_active_tasks": -1,
        "image_gen_daily_limit": 200,
        "sandbox_enabled": True,
        "sandbox_minutes_monthly": 120,
        "session_retention_days": -1,
        "priority_queue": True,
        "custom_personas": True,
    },
    Plan.ADMIN: {
        "credits_monthly": 999_999_999,
        "credits_reset": True,
        "max_personas": -1,
        "max_active_mcps": -1,
        "max_devices": -1,
        "max_active_tasks": -1,
        "image_gen_daily_limit": -1,
        "sandbox_enabled": True,
        "sandbox_minutes_monthly": -1,
        "session_retention_days": -1,
        "priority_queue": True,
        "custom_personas": True,
    },
    Plan.TESTER: {
        "credits_monthly": 999_999,
        "credits_reset": True,
        "max_personas": -1,
        "max_active_mcps": -1,
        "max_devices": -1,
        "max_active_tasks": -1,
        "image_gen_daily_limit": -1,
        "sandbox_enabled": True,
        "sandbox_minutes_monthly": -1,
        "session_retention_days": -1,
        "priority_queue": True,
        "custom_personas": True,
    },
}

# ── Credit cost table ────────────────────────────────────────────────

CREDIT_COSTS = {
    "text_input_1k": 1,       # per 1K input tokens
    "text_output_1k": 4,      # per 1K output tokens
    "voice_input_sec": 2,     # per second
    "voice_output_sec": 3,    # per second
    "image_gen": 30,          # per image
    "mcp_call": 2,            # per tool call
    "sandbox_min": 10,        # per minute
    "brave_search": 3,        # per query
    "google_maps": 3,         # per call
}


# ── Service ──────────────────────────────────────────────────────────

class SubscriptionService:
    """Firestore-backed subscription and credit manager."""

    def __init__(self, db: firestore.Client | None = None) -> None:
        self._db = db

    @property
    def db(self) -> firestore.Client:
        if self._db is None:
            self._db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        return self._db

    # ── Admin / Tester detection ─────────────────────────────────────

    def resolve_effective_plan(self, user_id: str, stored_plan: str | None = None) -> Plan:
        """Return the effective plan considering admin/tester overrides."""
        if user_id in settings.admin_uid_set:
            return Plan.ADMIN
        if user_id in settings.tester_uid_set:
            return Plan.TESTER
        return Plan(stored_plan) if stored_plan else Plan.FREE

    def is_override_user(self, user_id: str) -> bool:
        """True if user is admin or tester (bypasses credit checks)."""
        return user_id in settings.admin_uid_set or user_id in settings.tester_uid_set

    # ── Subscription CRUD ────────────────────────────────────────────

    async def get_or_create_subscription(self, user_id: str) -> dict:
        """Return the user's subscription doc, creating free tier if missing."""
        ref = self.db.collection(COLLECTION).document(user_id)
        snap = await asyncio.to_thread(ref.get)

        effective_plan = self.resolve_effective_plan(user_id)

        if snap.exists:
            data = snap.to_dict()
            # Override plan for admin/tester UIDs
            if effective_plan in (Plan.ADMIN, Plan.TESTER):
                data["plan"] = effective_plan.value
                data["_override"] = True
            return data

        # First-time user → create doc
        now = datetime.now(timezone.utc).isoformat()
        plan = effective_plan if effective_plan in (Plan.ADMIN, Plan.TESTER) else Plan.FREE
        sub = {
            "user_id": user_id,
            "plan": plan.value,
            "status": SubStatus.ACTIVE.value,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "current_period_start": now,
            "current_period_end": None,
            "cancel_at_period_end": False,
            "created_at": now,
            "updated_at": now,
        }
        await asyncio.to_thread(ref.set, sub)
        await self._init_credits(user_id, plan)
        logger.info("subscription_created", user_id=user_id, plan=plan.value)
        return sub

    async def update_plan(self, user_id: str, plan: Plan,
                          stripe_sub_id: str | None = None) -> dict:
        """Upgrade/downgrade a user's plan (called from Stripe webhook)."""
        ref = self.db.collection(COLLECTION).document(user_id)
        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "plan": plan.value,
            "status": SubStatus.ACTIVE.value,
            "stripe_subscription_id": stripe_sub_id,
            "updated_at": now,
        }
        await asyncio.to_thread(ref.update, updates)
        await self._reset_credits(user_id, plan)
        logger.info("subscription_updated", user_id=user_id, plan=plan.value)
        return {**updates}

    # ── Credit management ────────────────────────────────────────────

    async def _init_credits(self, user_id: str, plan: Plan) -> None:
        config = PLAN_CONFIG[plan]
        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        await asyncio.to_thread(ref.set, {
            "balance": config["credits_monthly"],
            "lifetime_used": 0,
            "period_used": 0,
            "period_limit": config["credits_monthly"],
            "bonus_credits": 0,
            "reset_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    async def _reset_credits(self, user_id: str, plan: Plan) -> None:
        config = PLAN_CONFIG[plan]
        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        snap = await asyncio.to_thread(ref.get)
        existing = snap.to_dict() if snap.exists else {}
        await asyncio.to_thread(ref.set, {
            "balance": config["credits_monthly"],
            "lifetime_used": existing.get("lifetime_used", 0),
            "period_used": 0,
            "period_limit": config["credits_monthly"],
            "bonus_credits": existing.get("bonus_credits", 0),
            "reset_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    async def get_credit_balance(self, user_id: str) -> dict:
        # Override users get infinite credits
        if self.is_override_user(user_id):
            plan = self.resolve_effective_plan(user_id)
            limit = PLAN_CONFIG[plan]["credits_monthly"]
            return {
                "balance": limit,
                "lifetime_used": 0,
                "period_used": 0,
                "period_limit": limit,
                "bonus_credits": 0,
                "unlimited": True,
            }

        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        snap = await asyncio.to_thread(ref.get)
        return snap.to_dict() if snap.exists else {"balance": 0, "period_limit": 0}

    async def deduct_credits(self, user_id: str, amount: int, action: str,
                             session_id: str = "", metadata: dict | None = None) -> bool:
        """Atomically deduct credits. Returns False if insufficient balance.

        Admin/tester UIDs always return True (no deduction).
        """
        if self.is_override_user(user_id):
            # Still log usage for analytics but don't deduct
            asyncio.create_task(self._log_usage(user_id, action, amount, session_id, metadata))
            return True

        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("credits")
            .document("current")
        )

        def _txn_deduct(txn, doc_ref):
            snap = doc_ref.get(transaction=txn)
            if not snap.exists:
                return False
            data = snap.to_dict()
            effective = data.get("balance", 0) + data.get("bonus_credits", 0)
            if effective < amount:
                return False

            bonus = data.get("bonus_credits", 0)
            now = datetime.now(timezone.utc).isoformat()
            if bonus >= amount:
                txn.update(doc_ref, {
                    "bonus_credits": bonus - amount,
                    "lifetime_used": data.get("lifetime_used", 0) + amount,
                    "period_used": data.get("period_used", 0) + amount,
                    "updated_at": now,
                })
            else:
                remainder = amount - bonus
                txn.update(doc_ref, {
                    "bonus_credits": 0,
                    "balance": data.get("balance", 0) - remainder,
                    "lifetime_used": data.get("lifetime_used", 0) + amount,
                    "period_used": data.get("period_used", 0) + amount,
                    "updated_at": now,
                })
            return True

        txn = self.db.transaction()

        @firestore.transactional
        def run_txn(transaction):
            return _txn_deduct(transaction, ref)

        success = await asyncio.to_thread(run_txn, txn)

        if success:
            asyncio.create_task(self._log_usage(user_id, action, amount, session_id, metadata))
        else:
            logger.warning("credits_insufficient", user_id=user_id, action=action, amount=amount)

        return success

    async def _log_usage(self, user_id: str, action: str, credits: int,
                         session_id: str, metadata: dict | None) -> None:
        try:
            ref = (
                self.db.collection(COLLECTION)
                .document(user_id)
                .collection("usage_log")
            )
            await asyncio.to_thread(ref.add, {
                "action": action,
                "credits": credits,
                "session_id": session_id,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            logger.debug("usage_log_write_failed", user_id=user_id, exc_info=True)

    # ── Feature flags ────────────────────────────────────────────────

    def get_feature_flags(self, user_id: str, plan: Plan | None = None) -> dict:
        """Return feature entitlements for a user's effective plan."""
        if plan is None:
            plan = self.resolve_effective_plan(user_id)
        config = PLAN_CONFIG.get(plan, PLAN_CONFIG[Plan.FREE])
        return {k: v for k, v in config.items() if k not in ("credits_monthly", "credits_reset")}

    def check_feature(self, user_id: str, feature: str, current_count: int = 0,
                      plan: Plan | None = None) -> bool:
        """Check if a user is within their plan's limit for a feature."""
        flags = self.get_feature_flags(user_id, plan)
        limit = flags.get(feature, 0)
        if limit == -1:
            return True
        return current_count < limit

    # ── Bonus / override credits ─────────────────────────────────────

    async def grant_bonus_credits(self, user_id: str, amount: int, reason: str = "") -> None:
        """Add bonus credits (never expire, used before plan balance)."""
        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        snap = await asyncio.to_thread(ref.get)
        if not snap.exists:
            # Ensure subscription exists first
            await self.get_or_create_subscription(user_id)
            snap = await asyncio.to_thread(ref.get)

        data = snap.to_dict() if snap.exists else {}
        current_bonus = data.get("bonus_credits", 0)
        await asyncio.to_thread(ref.update, {
            "bonus_credits": current_bonus + amount,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("bonus_credits_granted", user_id=user_id, amount=amount, reason=reason)

    async def set_override_credits(self, user_id: str, balance: int) -> None:
        """Manually set a user's credit balance (admin action)."""
        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("credits")
            .document("current")
        )
        snap = await asyncio.to_thread(ref.get)
        if not snap.exists:
            await self.get_or_create_subscription(user_id)

        await asyncio.to_thread(ref.update, {
            "balance": balance,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("credits_overridden", user_id=user_id, balance=balance)

    # ── Usage analytics ──────────────────────────────────────────────

    async def get_usage_summary(self, user_id: str, limit: int = 100) -> list[dict]:
        """Return recent usage log entries."""
        ref = (
            self.db.collection(COLLECTION)
            .document(user_id)
            .collection("usage_log")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        snaps = await asyncio.to_thread(lambda: list(ref.stream()))
        return [s.to_dict() for s in snaps]


# ── Module singleton ─────────────────────────────────────────────────

_service: SubscriptionService | None = None


def get_subscription_service() -> SubscriptionService:
    global _service
    if _service is None:
        _service = SubscriptionService()
    return _service
