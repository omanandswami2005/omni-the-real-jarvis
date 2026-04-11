"""Tests for billing API endpoints — status, usage, admin, checkout, portal."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth_middleware import AuthenticatedUser, get_current_user


# ── Helpers ───────────────────────────────────────────────────────────

FAKE_TOKEN = {"uid": "user1", "email": "u@test.com", "name": "User One", "picture": ""}
ADMIN_TOKEN = {"uid": "admin1", "email": "a@test.com", "name": "Admin", "picture": ""}


def _make_user(token):
    return AuthenticatedUser(token)


def _make_authed_client(token):
    """Return a TestClient with the auth dependency overridden."""
    async def _override():
        return _make_user(token)
    app.dependency_overrides[get_current_user] = _override
    return TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def authed_client():
    """TestClient WITHOUT lifespan (no ``with``) to avoid the
    ``_force_exit_delayed`` os._exit(0) that kills the test runner."""
    client = _make_authed_client(FAKE_TOKEN)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client():
    client = _make_authed_client(ADMIN_TOKEN)
    yield client
    app.dependency_overrides.clear()


# ── Mock the SubscriptionService ──────────────────────────────────────

def _mock_svc(plan="free", balance=500, unlimited=False, bonus=0):
    """Return a mock SubscriptionService with predictable return values."""
    svc = MagicMock()
    svc.get_or_create_subscription = AsyncMock(return_value={
        "user_id": "user1",
        "plan": plan,
        "status": "active",
        "stripe_customer_id": None,
        "cancel_at_period_end": False,
    })
    svc.get_credit_balance = AsyncMock(return_value={
        "balance": balance,
        "lifetime_used": 0,
        "period_used": 0,
        "period_limit": 500,
        "bonus_credits": bonus,
        "unlimited": unlimited,
    })
    svc.resolve_effective_plan = MagicMock(side_effect=lambda uid, p=None: __import__(
        "app.services.subscription_service", fromlist=["Plan"]).Plan(p or "free"))
    svc.get_feature_flags = MagicMock(return_value={
        "max_personas": 1, "max_active_mcps": 3, "max_devices": 1,
        "sandbox_enabled": False, "custom_personas": False,
    })
    svc.is_override_user = MagicMock(return_value=False)
    svc.get_usage_summary = AsyncMock(return_value=[
        {"action": "text_input_1k", "credits": 5, "timestamp": "2026-01-01T00:00:00Z"},
    ])
    svc.grant_bonus_credits = AsyncMock()
    svc.set_override_credits = AsyncMock()
    svc.update_plan = AsyncMock(return_value={"plan": plan})
    return svc


# ── GET /billing/status ──────────────────────────────────────────────

class TestBillingStatus:

    def test_status_returns_plan_and_credits(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/billing/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["plan"] == "free"
            assert data["credits"]["balance"] == 500
            assert "features" in data
            assert "plans" in data
            assert "credit_costs" in data
            assert data["is_override"] is False

    def test_status_includes_plan_comparison(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/billing/status")
            data = resp.json()
            plans = data["plans"]
            assert "free" in plans
            assert "pro" in plans
            assert "ultra" in plans
            # Admin/Tester plans should NOT be in the comparison
            assert "admin" not in plans
            assert "tester" not in plans


# ── GET /billing/usage ───────────────────────────────────────────────

class TestBillingUsage:

    def test_usage_returns_entries(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/billing/usage")
            assert resp.status_code == 200
            data = resp.json()
            assert "usage" in data
            assert len(data["usage"]) == 1


# ── POST /billing/checkout ───────────────────────────────────────────

class TestBillingCheckout:

    def test_checkout_returns_503_without_stripe_key(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = ""
            mock_settings.STRIPE_PRO_PRICE_ID = "price_pro"
            mock_settings.STRIPE_ULTRA_PRICE_ID = "price_ultra"
            resp = authed_client.post("/api/v1/billing/checkout?plan=pro")
            assert resp.status_code == 503

    def test_checkout_invalid_plan(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = "sk_test_fake"
            mock_settings.STRIPE_PRO_PRICE_ID = ""
            mock_settings.STRIPE_ULTRA_PRICE_ID = ""
            resp = authed_client.post("/api/v1/billing/checkout?plan=invalid")
            assert resp.status_code == 400


# ── POST /billing/portal ─────────────────────────────────────────────

class TestBillingPortal:

    def test_portal_returns_503_without_stripe_key(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = ""
            resp = authed_client.post("/api/v1/billing/portal")
            assert resp.status_code == 503

    def test_portal_no_billing_account(self, authed_client):
        mock = _mock_svc()
        mock.get_or_create_subscription = AsyncMock(return_value={
            "plan": "free", "status": "active", "stripe_customer_id": None,
        })
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = "sk_test_fake"
            resp = authed_client.post("/api/v1/billing/portal")
            assert resp.status_code == 400


# ── Admin endpoints ──────────────────────────────────────────────────

class TestAdminEndpoints:

    def test_grant_credits_requires_admin(self, authed_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.admin_uid_set = {"admin1"}
            mock_settings.tester_uid_set = set()
            resp = authed_client.post(
                "/api/v1/billing/admin/grant-credits?target_uid=u2&amount=100&reason=test"
            )
            assert resp.status_code == 403

    def test_grant_credits_as_admin(self, admin_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.admin_uid_set = {"admin1"}
            mock_settings.tester_uid_set = set()
            resp = admin_client.post(
                "/api/v1/billing/admin/grant-credits?target_uid=u2&amount=100&reason=promo"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["granted"] == 100
            assert data["target_uid"] == "u2"

    def test_grant_credits_missing_params(self, admin_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.admin_uid_set = {"admin1"}
            mock_settings.tester_uid_set = set()
            resp = admin_client.post("/api/v1/billing/admin/grant-credits")
            assert resp.status_code == 400

    def test_set_credits_as_admin(self, admin_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.admin_uid_set = {"admin1"}
            mock_settings.tester_uid_set = set()
            resp = admin_client.post(
                "/api/v1/billing/admin/set-credits?target_uid=u2&balance=9999"
            )
            assert resp.status_code == 200
            assert resp.json()["set_balance"] == 9999

    def test_set_plan_as_admin(self, admin_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.admin_uid_set = {"admin1"}
            mock_settings.tester_uid_set = set()
            resp = admin_client.post(
                "/api/v1/billing/admin/set-plan?target_uid=u2&plan=pro"
            )
            assert resp.status_code == 200
            assert resp.json()["plan"] == "pro"

    def test_set_plan_invalid_plan(self, admin_client):
        mock = _mock_svc()
        with patch("app.api.billing.get_subscription_service", return_value=mock), \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.settings") as mock_settings:
            mock_settings.admin_uid_set = {"admin1"}
            mock_settings.tester_uid_set = set()
            resp = admin_client.post(
                "/api/v1/billing/admin/set-plan?target_uid=u2&plan=enterprise"
            )
            assert resp.status_code == 400


# NOTE: X-Credits-Remaining / X-Plan headers are set by SubscriptionMiddleware
# which depends on request.state.user being set by the *real* auth middleware.
# The dependency-override approach bypasses request.state, so header tests
# live in tests/test_middleware/ instead.
