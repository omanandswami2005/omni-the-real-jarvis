"""Tests for feature gating — plan-based limits on personas, MCPs, plugins, tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth_middleware import AuthenticatedUser, get_current_user


# ── Helpers ───────────────────────────────────────────────────────────

FAKE_TOKEN = {"uid": "user1", "email": "u@test.com", "name": "User", "picture": ""}


def _make_user():
    return AuthenticatedUser(FAKE_TOKEN)


def _sub_mock(plan="free", balance=500, unlimited=False):
    """Subscription middleware mock — sets credits so usage gate doesn't block."""
    svc = MagicMock()
    svc.get_or_create_subscription = AsyncMock(return_value={
        "plan": plan, "status": "active", "stripe_customer_id": None,
        "cancel_at_period_end": False,
    })
    svc.get_credit_balance = AsyncMock(return_value={
        "balance": balance, "period_limit": 10000, "bonus_credits": 0,
        "unlimited": unlimited,
    })
    from app.services.subscription_service import Plan
    svc.resolve_effective_plan = MagicMock(return_value=Plan(plan))
    svc.get_feature_flags = MagicMock(
        side_effect=lambda uid, plan=None: _get_flags(plan))
    svc.is_override_user = MagicMock(return_value=unlimited)
    svc.check_feature = MagicMock(
        side_effect=lambda uid, feature, count, plan=None: _check(feature, count, plan))
    return svc


def _get_flags(plan):
    from app.services.subscription_service import PLAN_CONFIG, Plan as P
    effective = plan or P.FREE
    config = PLAN_CONFIG.get(effective, PLAN_CONFIG[P.FREE])
    return {k: v for k, v in config.items() if k not in ("credits_monthly", "credits_reset")}


def _check(feature, count, plan):
    from app.services.subscription_service import PLAN_CONFIG, Plan as P
    p = plan or P.FREE
    config = PLAN_CONFIG.get(p, PLAN_CONFIG[P.FREE])
    limit = config.get(feature, 0)
    if limit == -1:
        return True
    return count < limit


@pytest.fixture
def authed_client():
    async def _override():
        return _make_user()
    app.dependency_overrides[get_current_user] = _override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ── Persona gating ───────────────────────────────────────────────────

class TestPersonaGating:

    def test_create_persona_blocked_on_free_plan(self, authed_client):
        """Free plan has custom_personas=False → should get 403."""
        sub_mock = _sub_mock("free")
        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.personas.get_subscription_service", return_value=sub_mock):
            resp = authed_client.post("/api/v1/personas", json={
                "name": "Test Persona",
                "system_prompt": "You are a test persona",
            })
            assert resp.status_code == 403
            assert "custom personas" in resp.json()["detail"].lower() or "Custom personas" in resp.json()["detail"]


# ── MCP gating ────────────────────────────────────────────────────────

class TestMCPGating:

    def test_toggle_mcp_blocked_at_limit(self, authed_client):
        """When enabled MCP count >= max_active_mcps, toggling on should fail."""
        sub_mock = _sub_mock("free")  # free = max 3 MCPs
        mock_mgr = MagicMock()
        mock_mgr.get_mcp_config = MagicMock(return_value=MagicMock())
        mock_mgr.get_enabled_ids = MagicMock(return_value=["mcp1", "mcp2", "mcp3"])  # at limit

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_mcp_manager", return_value=mock_mgr):
            resp = authed_client.post("/api/v1/mcp/toggle", json={
                "mcp_id": "new_mcp", "enabled": True,
            })
            assert resp.status_code == 403
            assert "limit" in resp.json()["detail"].lower()

    def test_toggle_mcp_allowed_under_limit(self, authed_client):
        """When enabled count < limit, toggling on should succeed."""
        sub_mock = _sub_mock("free")
        mock_mgr = MagicMock()
        mock_mgr.get_mcp_config = MagicMock(return_value=MagicMock())
        mock_mgr.get_enabled_ids = MagicMock(return_value=["mcp1"])  # under limit (3)
        mock_mgr.toggle_mcp = AsyncMock(return_value=True)

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_mcp_manager", return_value=mock_mgr):
            resp = authed_client.post("/api/v1/mcp/toggle", json={
                "mcp_id": "new_mcp", "enabled": True,
            })
            assert resp.status_code == 200

    def test_toggle_mcp_disable_always_allowed(self, authed_client):
        """Disabling an MCP should never be blocked by limits."""
        sub_mock = _sub_mock("free")
        mock_mgr = MagicMock()
        mock_mgr.get_mcp_config = MagicMock(return_value=MagicMock())
        mock_mgr.toggle_mcp = AsyncMock(return_value=False)

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_mcp_manager", return_value=mock_mgr):
            resp = authed_client.post("/api/v1/mcp/toggle", json={
                "mcp_id": "mcp1", "enabled": False,
            })
            assert resp.status_code == 200

    def test_e2b_mcp_blocked_on_free_plan(self, authed_client):
        """Enabling an E2B MCP should fail when sandbox_enabled=False."""
        sub_mock = _sub_mock("free")
        mock_mgr = MagicMock()
        mock_mgr.get_mcp_config = MagicMock(return_value=MagicMock())
        mock_mgr.get_enabled_ids = MagicMock(return_value=[])  # under limit

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_subscription_service", return_value=sub_mock), \
             patch("app.api.mcp.get_mcp_manager", return_value=mock_mgr):
            resp = authed_client.post("/api/v1/mcp/toggle", json={
                "mcp_id": "e2b_sandbox", "enabled": True,
            })
            assert resp.status_code == 403
            assert "sandbox" in resp.json()["detail"].lower()


# ── Plugin gating ─────────────────────────────────────────────────────

class TestPluginGating:

    def test_toggle_plugin_blocked_at_limit(self, authed_client):
        """Enabling a plugin when at MCP limit should fail."""
        sub_mock = _sub_mock("free")  # max 3
        mock_registry = MagicMock()
        mock_registry.get_manifest = MagicMock(return_value=MagicMock(
            requires_auth=False, env_keys=[]
        ))
        mock_registry.get_enabled_ids = MagicMock(return_value=["p1", "p2", "p3"])

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.plugins.get_subscription_service", return_value=sub_mock), \
             patch("app.api.plugins.get_plugin_registry", return_value=mock_registry):
            resp = authed_client.post("/api/v1/plugins/toggle", json={
                "plugin_id": "new_plugin", "enabled": True,
            })
            assert resp.status_code == 403


# ── Task gating ───────────────────────────────────────────────────────

class TestTaskGating:

    def test_create_task_blocked_at_limit(self, authed_client):
        """Creating a task when active count >= max_active_tasks should fail."""
        sub_mock = _sub_mock("free")  # max 3 active tasks

        # Create mock tasks at the limit
        from unittest.mock import PropertyMock
        mock_task = MagicMock()
        mock_task.status.value = "running"
        mock_orchestrator = MagicMock()
        mock_orchestrator.list_tasks = AsyncMock(return_value=[mock_task, mock_task, mock_task])

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.tasks.get_subscription_service", return_value=sub_mock), \
             patch("app.api.tasks.get_task_orchestrator", return_value=mock_orchestrator):
            resp = authed_client.post("/api/v1/tasks/", json={
                "description": "Test task",
            })
            assert resp.status_code == 403
            assert "task limit" in resp.json()["detail"].lower()


# ── Desktop/sandbox gating ────────────────────────────────────────────

class TestDesktopGating:

    def test_start_desktop_blocked_on_free(self, authed_client):
        """Starting E2B desktop should fail on free plan (sandbox_enabled=False)."""
        sub_mock = _sub_mock("free")

        with patch("app.middleware.subscription_middleware.get_subscription_service", return_value=sub_mock), \
             patch("app.api.tasks.get_subscription_service", return_value=sub_mock):
            resp = authed_client.post("/api/v1/tasks/desktop/start")
            assert resp.status_code == 403
            assert "sandbox" in resp.json()["detail"].lower()
