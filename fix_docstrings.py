import re

with open("backend/app/tools/desktop_tools.py", "r") as f:
    content = f.read()

# Add missing docstrings. I need to make sure I get 80% coverage.
missing = {
    "_mock_svc": '"""Mock the desktop service for testing."""',
    "_queue_screenshot": '"""Queue a screenshot to be sent to the live API."""',
    "drain_pending_screenshots": '"""Drain the pending screenshot queue for a user."""',
}

# _queue_screenshot
content = content.replace(
    'def _queue_screenshot(user_id: str, b64: str, mime_type: str = "image/png", description: str = "") -> None:\n    _pending_screenshots',
    'def _queue_screenshot(user_id: str, b64: str, mime_type: str = "image/png", description: str = "") -> None:\n    """Queue a screenshot to be sent to the live API."""\n    _pending_screenshots'
)

# drain_pending_screenshots
content = content.replace(
    'def drain_pending_screenshots(user_id: str) -> list[dict]:\n    return _pending_screenshots',
    'def drain_pending_screenshots(user_id: str) -> list[dict]:\n    """Drain the pending screenshot queue for a user."""\n    return _pending_screenshots'
)

# get_desktop_tools
content = content.replace(
    'def get_desktop_tools() -> list[FunctionTool]:\n    global _DESKTOP_TOOLS',
    'def get_desktop_tools() -> list[FunctionTool]:\n    """Get all available desktop tools."""\n    global _DESKTOP_TOOLS'
)

with open("backend/app/tools/desktop_tools.py", "w") as f:
    f.write(content)


with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content_test = f.read()

content_test = content_test.replace(
    'def _mock_svc():\n    svc = MagicMock()',
    'def _mock_svc():\n    """Mock the desktop service for testing."""\n    svc = MagicMock()'
)

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content_test)
