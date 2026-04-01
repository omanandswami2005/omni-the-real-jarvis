import re

with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content = f.read()

classes = [
    "TestDesktopScreenshot",
    "TestDesktopClick",
    "TestDesktopType",
    "TestDesktopHotkey",
    "TestDesktopLaunch",
    "TestDesktopBash",
    "TestDesktopClipboardWrite",
    "TestGetDesktopTools"
]

for cls in classes:
    content = content.replace(f"class {cls}:\n", f'class {cls}:\n    """Tests for {cls.replace("Test", "")}."""\n')

# Methods
content = content.replace("async def test_returns_image", '"""Test that screenshot enqueues image payload."""\n    async def test_returns_image')
content = content.replace("async def test_sends_coordinates", '"""Test that clicking sends coordinates."""\n    async def test_sends_coordinates')
content = content.replace("async def test_sends_text", '"""Test that typing sends text."""\n    async def test_sends_text')
content = content.replace("async def test_sends_key_combo", '"""Test that hotkey sends key combos."""\n    async def test_sends_key_combo')
content = content.replace("async def test_sends_app_name", '"""Test that launch sends app name."""\n    async def test_sends_app_name')
content = content.replace("async def test_runs_command", '"""Test that bash runs command."""\n    async def test_runs_command')
content = content.replace("async def test_writes_clipboard", '"""Test that clipboard write sends safely encoded command."""\n    async def test_writes_clipboard')
content = content.replace("def test_returns_twenty_tools", '"""Test that exactly 27 tools are returned."""\n    def test_returns_twenty_tools')
content = content.replace("def test_tool_names", '"""Test that tools have expected names."""\n    def test_tool_names')

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content)
