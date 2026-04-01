"""Tests for the E2B desktop ADK tools."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.desktop_tools import (
    desktop_bash,
    desktop_click,
    desktop_clipboard_write,
    desktop_hotkey,
    desktop_launch,
    desktop_screenshot,
    desktop_type,
    get_desktop_tools,
)

_SVC = "app.tools.desktop_tools.get_e2b_desktop_service"


def _mock_svc():
    """Mock desktop service."""
    """Mock the desktop service for testing."""
    svc = MagicMock()
    svc.screenshot = AsyncMock(return_value=b"\x89PNG fake")
    svc.left_click = AsyncMock()
    svc.right_click = AsyncMock()
    svc.double_click = AsyncMock()
    svc.write_text = AsyncMock()
    svc.press_keys = AsyncMock()
    svc.launch_app = AsyncMock()
    svc.run_command = AsyncMock(return_value={"stdout": "hello", "stderr": "", "exit_code": 0})
    return svc


class TestDesktopScreenshot:
    """Tests."""
    """Tests for DesktopScreenshot."""
    @pytest.mark.asyncio
    @patch(_SVC)
    @patch("app.tools.desktop_tools._queue_screenshot")
    async def test_returns_image(self, mock_queue, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_screenshot(user_id="u1")
        assert "message" in result
        svc.screenshot.assert_awaited_once_with("u1")
        # Ensure it enqueues the base64 image
        mock_queue.assert_called_once_with("u1", "iVBORyBmYWtl", description="Desktop screenshot")


class TestDesktopClick:
    """Tests."""
    """Tests for DesktopClick."""
    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_sends_coordinates(self, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_click(x=100, y=200, user_id="u1")
        assert result["clicked"] is True
        assert result["x"] == 100 and result["y"] == 200
        svc.left_click.assert_awaited_once_with("u1", 100, 200)


class TestDesktopType:
    """Tests."""
    """Tests for DesktopType."""
    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_sends_text(self, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_type(text="hello", user_id="u1")
        assert result["typed"] is True
        svc.write_text.assert_awaited_once_with("u1", "hello")


class TestDesktopHotkey:
    """Tests."""
    """Tests for DesktopHotkey."""
    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_sends_key_combo(self, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_hotkey(keys=["ctrl", "c"], user_id="u1")
        assert result["pressed"] is True
        svc.press_keys.assert_awaited_once_with("u1", ["ctrl", "c"])


class TestDesktopLaunch:
    """Tests."""
    """Tests for DesktopLaunch."""
    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_sends_app_name(self, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_launch(app_name="firefox", user_id="u1")
        assert result["launched"] is True
        svc.launch_app.assert_awaited_once_with("u1", "firefox")


class TestDesktopBash:
    """Tests."""
    """Tests for DesktopBash."""
    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_runs_command(self, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_bash(command="echo hi", user_id="u1")
        assert result["stdout"] == "hello"
        svc.run_command.assert_awaited_once_with("u1", "echo hi")


class TestDesktopClipboardWrite:
    """Tests."""
    """Tests for DesktopClipboardWrite."""
    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_writes_clipboard(self, mock_get_svc):
        """Test case."""
        """Test method."""
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        text = "hello '\"world\"'\n$(id)"
        b64_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        result = await desktop_clipboard_write(text=text, user_id="u1")
        assert result["copied"] is True
        assert result["length"] == len(text)

        expected_cmd = (
            f"set -o pipefail; echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || "
            f"{{ set -o pipefail; echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null; }}"
        )
        svc.run_command.assert_awaited_once_with("u1", expected_cmd)

class TestGetDesktopTools:
    """Tests."""
    """Tests for GetDesktopTools."""
    def test_returns_twenty_tools(self):
        """Test case."""
        """Test method."""
        tools = get_desktop_tools()
        assert len(tools) == 27

    def test_tool_names(self):
        """Test case."""
        """Test method."""
        tools = get_desktop_tools()
        names = {t.name for t in tools}
        assert "desktop_screenshot" in names
        assert "desktop_click" in names
        assert "desktop_bash" in names
        assert "start_desktop" in names
        assert "stop_desktop" in names