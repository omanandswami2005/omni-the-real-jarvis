"""Tests for SubscriptionService — plan resolution, credits, feature gating."""

import asyncio

import pytest
from unittest.mock import patch

from app.services.subscription_service import (
    SubscriptionService,
    Plan,
    PLAN_CONFIG,
    CREDIT_COSTS,
)


# ── Fake Firestore (with subcollections, transactions, add, limit, order_by) ──


class FakeDocSnap:
    def __init__(self, doc_id: str, data: dict, *, exists: bool = True):
        self.id = doc_id
        self.exists = exists
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeTransaction:
    """Minimal transaction mock — update delegates to the doc ref."""

    def update(self, doc_ref, updates):
        doc_ref.update(updates)


class _FakeDocRef:
    def __init__(self, store: dict, path: str):
        self._store = store
        self._path = path

    def set(self, data, **kw):
        self._store[self._path] = dict(data)

    def get(self, **kw):
        if self._path in self._store:
            doc_id = self._path.rsplit("/", 1)[-1]
            return FakeDocSnap(doc_id, self._store[self._path])
        doc_id = self._path.rsplit("/", 1)[-1]
        return FakeDocSnap(doc_id, {}, exists=False)

    def update(self, updates, **kw):
        if self._path not in self._store:
            raise Exception(f"Document not found: {self._path}")
        self._store[self._path].update(updates)

    def delete(self):
        self._store.pop(self._path, None)

    def collection(self, name: str):
        return _FakeCollectionRef(self._store, f"{self._path}/{name}")


class _FakeCollectionRef:
    def __init__(self, store: dict, prefix: str):
        self._store = store
        self._prefix = prefix

    def document(self, doc_id: str):
        return _FakeDocRef(self._store, f"{self._prefix}/{doc_id}")

    def add(self, data):
        import uuid
        doc_id = uuid.uuid4().hex[:12]
        path = f"{self._prefix}/{doc_id}"
        self._store[path] = dict(data)
        return (None, _FakeDocRef(self._store, path))

    def where(self, field=None, op=None, value=None, **kw):
        return _FakeQuery(self._store, self._prefix, field, op, value)

    def order_by(self, field, direction=None):
        return _FakeQuery(self._store, self._prefix, order_field=field,
                          descending=(direction is not None))

    def limit(self, n):
        return _FakeQuery(self._store, self._prefix, limit_n=n)

    def stream(self):
        results = []
        for path, data in self._store.items():
            if path.startswith(self._prefix + "/"):
                remainder = path[len(self._prefix) + 1:]
                if "/" not in remainder:
                    results.append(FakeDocSnap(remainder, data))
        return results


class _FakeQuery:
    def __init__(self, store, prefix, field=None, op=None, value=None,
                 order_field=None, descending=False, limit_n=None):
        self._store = store
        self._prefix = prefix
        self._field = field
        self._op = op
        self._value = value
        self._order_field = order_field
        self._descending = descending
        self._limit_n = limit_n

    def where(self, *a, **kw):
        return self

    def order_by(self, field, direction=None):
        self._order_field = field
        self._descending = (direction is not None)
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def stream(self):
        results = []
        for path, data in self._store.items():
            if path.startswith(self._prefix + "/"):
                remainder = path[len(self._prefix) + 1:]
                if "/" not in remainder:
                    if self._field and self._op == "==" and data.get(self._field) != self._value:
                        continue
                    results.append(FakeDocSnap(remainder, data))
        if self._order_field:
            results.sort(key=lambda s: s._data.get(self._order_field, ""),
                         reverse=self._descending)
        if self._limit_n is not None:
            results = results[:self._limit_n]
        return results


class FakeFirestore:
    """In-memory Firestore supporting nested subcollections and transactions."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def collection(self, name: str):
        return _FakeCollectionRef(self._store, name)

    def transaction(self):
        return FakeTransaction()


# ── Helpers ───────────────────────────────────────────────────────────

def _settings_ctx(admin_uids="", tester_uids=""):
    """Replace the ``settings`` object inside subscription_service module."""
    class FakeSettings:
        GOOGLE_CLOUD_PROJECT = ""
        @property
        def admin_uid_set(self):
            return {u.strip() for u in admin_uids.split(",") if u.strip()}
        @property
        def tester_uid_set(self):
            return {u.strip() for u in tester_uids.split(",") if u.strip()}

    return patch("app.services.subscription_service.settings", FakeSettings())


def _patch_transactional():
    """Patch ``@firestore.transactional`` to simply call the function."""
    def fake_transactional(fn):
        def wrapper(transaction):
            return fn(transaction)
        return wrapper
    return patch("google.cloud.firestore.transactional", new=fake_transactional)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def fake_db():
    return FakeFirestore()

@pytest.fixture
def svc(fake_db):
    return SubscriptionService(db=fake_db)


# ══════════════════════════════════════════════════════════════════════
# Plan Resolution
# ══════════════════════════════════════════════════════════════════════

class TestPlanResolution:

    def test_default_plan_is_free(self, svc):
        with _settings_ctx():
            assert svc.resolve_effective_plan("random_user") == Plan.FREE

    def test_stored_plan_pro(self, svc):
        with _settings_ctx():
            assert svc.resolve_effective_plan("random_user", "pro") == Plan.PRO

    def test_admin_uid_overrides_stored_plan(self, svc):
        with _settings_ctx(admin_uids="admin1"):
            assert svc.resolve_effective_plan("admin1", "free") == Plan.ADMIN

    def test_tester_uid_overrides_stored_plan(self, svc):
        with _settings_ctx(tester_uids="tester1"):
            assert svc.resolve_effective_plan("tester1", "pro") == Plan.TESTER

    def test_admin_takes_priority_over_tester(self, svc):
        with _settings_ctx(admin_uids="user1", tester_uids="user1"):
            assert svc.resolve_effective_plan("user1") == Plan.ADMIN

    def test_is_override_user_admin(self, svc):
        with _settings_ctx(admin_uids="admin1"):
            assert svc.is_override_user("admin1") is True
            assert svc.is_override_user("other") is False

    def test_is_override_user_tester(self, svc):
        with _settings_ctx(tester_uids="tester1"):
            assert svc.is_override_user("tester1") is True


# ══════════════════════════════════════════════════════════════════════
# Subscription CRUD
# ══════════════════════════════════════════════════════════════════════

class TestSubscriptionCRUD:

    @pytest.mark.asyncio
    async def test_create_new_user_free(self, svc):
        with _settings_ctx():
            sub = await svc.get_or_create_subscription("user1")
            assert sub["user_id"] == "user1"
            assert sub["plan"] == "free"
            assert sub["status"] == "active"
            assert sub["stripe_customer_id"] is None

    @pytest.mark.asyncio
    async def test_existing_user_returns_same(self, svc):
        with _settings_ctx():
            sub1 = await svc.get_or_create_subscription("user1")
            sub2 = await svc.get_or_create_subscription("user1")
            assert sub1["plan"] == sub2["plan"] == "free"

    @pytest.mark.asyncio
    async def test_admin_user_gets_admin_plan(self, svc):
        with _settings_ctx(admin_uids="admin1"):
            sub = await svc.get_or_create_subscription("admin1")
            assert sub["plan"] == "admin"

    @pytest.mark.asyncio
    async def test_tester_user_gets_tester_plan(self, svc):
        with _settings_ctx(tester_uids="tester1"):
            sub = await svc.get_or_create_subscription("tester1")
            assert sub["plan"] == "tester"

    @pytest.mark.asyncio
    async def test_existing_user_overridden_to_admin(self, svc):
        with _settings_ctx():
            await svc.get_or_create_subscription("user1")
        with _settings_ctx(admin_uids="user1"):
            sub = await svc.get_or_create_subscription("user1")
            assert sub["plan"] == "admin"
            assert sub.get("_override") is True

    @pytest.mark.asyncio
    async def test_update_plan_pro(self, svc):
        with _settings_ctx():
            await svc.get_or_create_subscription("user1")
            result = await svc.update_plan("user1", Plan.PRO, "stripe_sub_123")
            assert result["plan"] == "pro"
            assert result["stripe_subscription_id"] == "stripe_sub_123"


# ══════════════════════════════════════════════════════════════════════
# Credit Management
# ══════════════════════════════════════════════════════════════════════

class TestCredits:

    @pytest.mark.asyncio
    async def test_initial_credits_match_free_plan(self, svc):
        with _settings_ctx():
            await svc.get_or_create_subscription("user1")
            credits = await svc.get_credit_balance("user1")
            assert credits["balance"] == PLAN_CONFIG[Plan.FREE]["credits_monthly"]
            assert credits["period_limit"] == PLAN_CONFIG[Plan.FREE]["credits_monthly"]
            assert credits.get("bonus_credits", 0) == 0

    @pytest.mark.asyncio
    async def test_override_user_gets_unlimited(self, svc):
        with _settings_ctx(admin_uids="admin1"):
            credits = await svc.get_credit_balance("admin1")
            assert credits["unlimited"] is True
            assert credits["balance"] == PLAN_CONFIG[Plan.ADMIN]["credits_monthly"]

    @pytest.mark.asyncio
    async def test_deduct_credits_success(self, svc):
        with _settings_ctx(), _patch_transactional():
            await svc.get_or_create_subscription("user1")
            result = await svc.deduct_credits("user1", 10, "text_input_1k")
            assert result is True
            credits = await svc.get_credit_balance("user1")
            assert credits["balance"] == PLAN_CONFIG[Plan.FREE]["credits_monthly"] - 10
            assert credits["period_used"] == 10
            assert credits["lifetime_used"] == 10

    @pytest.mark.asyncio
    async def test_deduct_credits_insufficient(self, svc):
        with _settings_ctx(), _patch_transactional():
            await svc.get_or_create_subscription("user1")
            result = await svc.deduct_credits("user1", 99999, "text_input_1k")
            assert result is False

    @pytest.mark.asyncio
    async def test_deduct_credits_override_always_succeeds(self, svc):
        with _settings_ctx(admin_uids="admin1"):
            result = await svc.deduct_credits("admin1", 999999, "text_input_1k")
            assert result is True

    @pytest.mark.asyncio
    async def test_deduct_uses_bonus_first(self, svc):
        with _settings_ctx(), _patch_transactional():
            await svc.get_or_create_subscription("user1")
            await svc.grant_bonus_credits("user1", 100, "test bonus")
            credits_before = await svc.get_credit_balance("user1")
            orig_balance = credits_before["balance"]
            assert credits_before["bonus_credits"] == 100

            await svc.deduct_credits("user1", 50, "test")
            credits_after = await svc.get_credit_balance("user1")
            assert credits_after["bonus_credits"] == 50
            assert credits_after["balance"] == orig_balance

    @pytest.mark.asyncio
    async def test_deduct_spills_from_bonus_to_balance(self, svc):
        with _settings_ctx(), _patch_transactional():
            await svc.get_or_create_subscription("user1")
            await svc.grant_bonus_credits("user1", 30, "test")
            await svc.deduct_credits("user1", 50, "test")
            credits = await svc.get_credit_balance("user1")
            assert credits["bonus_credits"] == 0
            assert credits["balance"] == PLAN_CONFIG[Plan.FREE]["credits_monthly"] - 20

    @pytest.mark.asyncio
    async def test_grant_bonus_credits(self, svc):
        with _settings_ctx():
            await svc.get_or_create_subscription("user1")
            await svc.grant_bonus_credits("user1", 500, "promo")
            credits = await svc.get_credit_balance("user1")
            assert credits["bonus_credits"] == 500

    @pytest.mark.asyncio
    async def test_set_override_credits(self, svc):
        with _settings_ctx():
            await svc.get_or_create_subscription("user1")
            await svc.set_override_credits("user1", 9999)
            credits = await svc.get_credit_balance("user1")
            assert credits["balance"] == 9999

    @pytest.mark.asyncio
    async def test_reset_credits_on_plan_upgrade(self, svc):
        with _settings_ctx(), _patch_transactional():
            await svc.get_or_create_subscription("user1")
            await svc.deduct_credits("user1", 100, "test")
            credits = await svc.get_credit_balance("user1")
            assert credits["balance"] == PLAN_CONFIG[Plan.FREE]["credits_monthly"] - 100

            await svc.update_plan("user1", Plan.PRO)
            credits = await svc.get_credit_balance("user1")
            assert credits["balance"] == PLAN_CONFIG[Plan.PRO]["credits_monthly"]
            assert credits["period_used"] == 0

    @pytest.mark.asyncio
    async def test_credit_balance_nonexistent_user(self, svc):
        with _settings_ctx():
            credits = await svc.get_credit_balance("nonexistent")
            assert credits["balance"] == 0
            assert credits["period_limit"] == 0


# ══════════════════════════════════════════════════════════════════════
# Feature Flags
# ══════════════════════════════════════════════════════════════════════

class TestFeatureFlags:

    def test_free_plan_flags(self, svc):
        with _settings_ctx():
            flags = svc.get_feature_flags("random_user")
            assert flags["max_personas"] == 1
            assert flags["max_active_mcps"] == 3
            assert flags["max_devices"] == 1
            assert flags["sandbox_enabled"] is False
            assert flags["custom_personas"] is False

    def test_pro_plan_flags(self, svc):
        flags = svc.get_feature_flags("user1", Plan.PRO)
        assert flags["max_personas"] == 4
        assert flags["max_active_mcps"] == 10
        assert flags["sandbox_enabled"] is True

    def test_ultra_plan_flags(self, svc):
        flags = svc.get_feature_flags("user1", Plan.ULTRA)
        assert flags["max_personas"] == -1
        assert flags["max_active_mcps"] == -1
        assert flags["sandbox_enabled"] is True
        assert flags["custom_personas"] is True

    def test_admin_plan_flags(self, svc):
        flags = svc.get_feature_flags("user1", Plan.ADMIN)
        assert flags["max_personas"] == -1
        assert flags["max_devices"] == -1
        assert flags["sandbox_enabled"] is True

    def test_check_feature_within_limit(self, svc):
        assert svc.check_feature("user1", "max_personas", 0, Plan.FREE) is True

    def test_check_feature_at_limit(self, svc):
        assert svc.check_feature("user1", "max_personas", 1, Plan.FREE) is False

    def test_check_feature_unlimited(self, svc):
        assert svc.check_feature("user1", "max_personas", 9999, Plan.ULTRA) is True


# ══════════════════════════════════════════════════════════════════════
# Usage Log
# ══════════════════════════════════════════════════════════════════════

class TestUsageLog:

    @pytest.mark.asyncio
    async def test_usage_log_written_on_deduction(self, svc):
        with _settings_ctx(), _patch_transactional():
            await svc.get_or_create_subscription("user1")
            await svc.deduct_credits("user1", 10, "text_input_1k", session_id="s1")
            await asyncio.sleep(0.1)
            entries = await svc.get_usage_summary("user1")
            assert len(entries) >= 1
            assert entries[0]["action"] == "text_input_1k"
            assert entries[0]["credits"] == 10

    @pytest.mark.asyncio
    async def test_usage_summary_empty(self, svc):
        entries = await svc.get_usage_summary("nonexistent")
        assert entries == []


# ══════════════════════════════════════════════════════════════════════
# Plan Config Sanity
# ══════════════════════════════════════════════════════════════════════

class TestPlanConfig:

    def test_all_plans_have_required_keys(self):
        required_keys = {
            "credits_monthly", "max_personas", "max_active_mcps",
            "max_devices", "max_active_tasks", "image_gen_daily_limit",
            "sandbox_enabled",
        }
        for plan, config in PLAN_CONFIG.items():
            for key in required_keys:
                assert key in config, f"Plan {plan.value} missing key {key}"

    def test_higher_plans_have_more_credits(self):
        assert PLAN_CONFIG[Plan.FREE]["credits_monthly"] < PLAN_CONFIG[Plan.PRO]["credits_monthly"]
        assert PLAN_CONFIG[Plan.PRO]["credits_monthly"] < PLAN_CONFIG[Plan.ULTRA]["credits_monthly"]

    def test_credit_costs_are_positive(self):
        for action, cost in CREDIT_COSTS.items():
            assert cost > 0, f"Credit cost for {action} should be positive"

