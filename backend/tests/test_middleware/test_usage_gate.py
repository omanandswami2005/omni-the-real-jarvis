"""Tests for UsageGateMiddleware — blocks 402 when credits exhausted."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth_middleware import AuthenticatedUser, get_current_user


# -- Helpers ---------------------------------------------------------------

FAKE_TOKEN = {"uid": "user1", "email": "u@test.com", "name": "User", "picture": ""}
AUTH_HEADER = {"Authorization": "Bearer fake_token_for_test"}


def _make_user():
    return AuthenticatedUser(FAKE_TOKEN)


def _mock_svc(balance=0, bonus=0, unlimited=False, plan="free"):
    svc = MagicMock()
    svc.get_or_create_subscription = AsyncMock(return_value={
        "plan": plan, "status": "active", "stripe_customer_id": None,
        "cancel_at_period_end": False,
    })
    svc.get_credit_balance = AsyncMock(return_value={
        "balance": balance,
        "period_limit": 500,
        "bonus_credits": bonus,
        "unlimited": unlimited,
    })
    svc.resolve_effective_plan = MagicMock(
        return_value=__import__("app.services.subscription_service", fromlist=["Plan"]).Plan(plan))
    svc.get_feature_flags = MagicMock(return_value={
        "max_personas": 1, "max_active_mcps": 3, "max_devices": 1,
        "sandbox_enabled": False,
    })
    svc.is_override_user = MagicMock(return_value=unlimited)
    return svc


def _firebase_patches():
    """Patch Firebase verification so AuthMiddleware sets request.state.user."""
    return (
        patch("app.middleware.auth_middleware._get_firebase_app", return_value=MagicMock()),
        patch("app.middleware.auth_middleware.firebase_auth.verify_id_token", return_value=FAKE_TOKEN),
    )


@pytest.fixture
def authed_client():
    async def _override():
        return _make_user()
    app.dependency_overrides[get_current_user] = _override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# -- Tests -----------------------------------------------------------------

class TestUsageGate:

    def test_blocks_when_credits_exhausted(self, authed_client):
        """Requests should get HTTP 402 when balance + bonus <= 0."""
        mock = _mock_svc(balance=0, bonus=0)
        p1, p2 = _firebase_patches()
        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/personas", headers=AUTH_HEADER)
            assert resp.status_code == 402
            data = resp.json()
            assert data["error"] == "credits_exhausted"
            assert "upgrade_url" in data

    def test_allows_when_credits_remain(self, authed_client):
        """Requests should pass when user has credits."""
        mock = _mock_svc(balance=100)
        p1, p2 = _firebase_patches()
        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/personas", headers=AUTH_HEADER)
            assert resp.status_code != 402

    def test_allows_bonus_credits(self, authed_client):
        """Bonus credits should prevent blocking."""
        mock = _mock_svc(balance=0, bonus=50)
        p1, p2 = _firebase_patches()
        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/personas", headers=AUTH_HEADER)
            assert resp.status_code != 402

    def test_allows_unlimited_users(self, authed_client):
        """Override users (admin/tester) with unlimited=True should always pass."""
        mock = _mock_svc(balance=0, bonus=0, unlimited=True)
        p1, p2 = _firebase_patches()
        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/personas", headers=AUTH_HEADER)
            assert resp.status_code != 402

    def test_exempt_paths_always_pass(self, authed_client):
        """Billing, auth, health, and docs paths should never be blocked."""
        mock = _mock_svc(balance=0, bonus=0)
        p1, p2 = _firebase_patches()
        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/health", headers=AUTH_HEADER)
            assert resp.status_code != 402

        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock), \
             patch("app.api.billing.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/billing/status", headers=AUTH_HEADER)
            assert resp.status_code != 402

    def test_402_response_contains_plan_info(self, authed_client):
        mock = _mock_svc(balance=0, bonus=0, plan="free")
        p1, p2 = _firebase_patches()
        with p1, p2, \
             patch("app.middleware.subscription_middleware.get_subscription_service", return_value=mock):
            resp = authed_client.get("/api/v1/personas", headers=AUTH_HEADER)
            assert resp.status_code == 402
            data = resp.json()
            assert data["plan"] == "free"
            assert data["upgrade_url"] == "/settings?tab=Billing"
