with open("backend/app/tools/desktop_tools.py", "r") as f:
    content = f.read()

# Add missing docstrings. I need to make sure I get 80% coverage.
missing = {
    "_mock_svc": '"""Mock the desktop service for testing."""',
    "_queue_screenshot": '"""Queue a screenshot to be sent to the live API."""',
    "drain_pending_screenshots": '"""Drain the pending screenshot queue for a user."""',
}

# _queue_screenshot
search_queue = 'def _queue_screenshot(user_id: str, b64: str, mime_type: str = "image/png", description: str = "") -> None:\n    _pending_screenshots'
if search_queue not in content:
    raise RuntimeError("Failed to find _queue_screenshot replacement target")
content = content.replace(
    search_queue,
    'def _queue_screenshot(user_id: str, b64: str, mime_type: str = "image/png", description: str = "") -> None:\n    """Queue a screenshot to be sent to the live API."""\n    _pending_screenshots'
)

# drain_pending_screenshots
search_drain = 'def drain_pending_screenshots(user_id: str) -> list[dict]:\n    return _pending_screenshots'
if search_drain not in content:
    raise RuntimeError("Failed to find drain_pending_screenshots replacement target")
content = content.replace(
    search_drain,
    'def drain_pending_screenshots(user_id: str) -> list[dict]:\n    """Drain the pending screenshot queue for a user."""\n    return _pending_screenshots'
)

# get_desktop_tools
search_get_tools = 'def get_desktop_tools() -> list[FunctionTool]:\n    global _DESKTOP_TOOLS'
if search_get_tools not in content:
    raise RuntimeError("Failed to find get_desktop_tools replacement target")
content = content.replace(
    search_get_tools,
    'def get_desktop_tools() -> list[FunctionTool]:\n    """Get all available desktop tools."""\n    global _DESKTOP_TOOLS'
)

with open("backend/app/tools/desktop_tools.py", "w") as f:
    f.write(content)


with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content_test = f.read()

search_mock_svc = 'def _mock_svc():\n    svc = MagicMock()'
if search_mock_svc not in content_test:
    raise RuntimeError("Failed to find 'def _mock_svc()' replacement target in test file")

content_test = content_test.replace(
    search_mock_svc,
    'def _mock_svc():\n    """Mock the desktop service for testing."""\n    svc = MagicMock()'
)

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content_test)