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

# Methods - insert docstrings as first line inside function body
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)

    # Check if this is a test function definition
    stripped = line.strip()
    if stripped.startswith("async def test_returns_image") or stripped.startswith("def test_returns_image"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that screenshot enqueues image payload."""')
    elif stripped.startswith("async def test_sends_coordinates") or stripped.startswith("def test_sends_coordinates"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that clicking sends coordinates."""')
    elif stripped.startswith("async def test_sends_text") or stripped.startswith("def test_sends_text"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that typing sends text."""')
    elif stripped.startswith("async def test_sends_key_combo") or stripped.startswith("def test_sends_key_combo"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that hotkey sends key combos."""')
    elif stripped.startswith("async def test_sends_app_name") or stripped.startswith("def test_sends_app_name"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that launch sends app name."""')
    elif stripped.startswith("async def test_runs_command") or stripped.startswith("def test_runs_command"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that bash runs command."""')
    elif stripped.startswith("async def test_writes_clipboard") or stripped.startswith("def test_writes_clipboard"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that clipboard write sends safely encoded command."""')
    elif stripped.startswith("def test_returns_twenty_tools"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that exactly 27 tools are returned."""')
    elif stripped.startswith("def test_tool_names"):
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * (spaces + 4) + '"""Test that tools have expected names."""')

    i += 1

content = '\n'.join(new_lines)

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content)