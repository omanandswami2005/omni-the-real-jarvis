import ast

with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content = f.read()

# revert previous script changes for methods
content = content.replace('"""Test that screenshot enqueues image payload."""\n    async def test_returns_image', 'async def test_returns_image')
content = content.replace('"""Test that clicking sends coordinates."""\n    async def test_sends_coordinates', 'async def test_sends_coordinates')
content = content.replace('"""Test that typing sends text."""\n    async def test_sends_text', 'async def test_sends_text')
content = content.replace('"""Test that hotkey sends key combos."""\n    async def test_sends_key_combo', 'async def test_sends_key_combo')
content = content.replace('"""Test that launch sends app name."""\n    async def test_sends_app_name', 'async def test_sends_app_name')
content = content.replace('"""Test that bash runs command."""\n    async def test_runs_command', 'async def test_runs_command')
content = content.replace('"""Test that clipboard write sends safely encoded command."""\n    async def test_writes_clipboard', 'async def test_writes_clipboard')
content = content.replace('"""Test that exactly 27 tools are returned."""\n    def test_returns_twenty_tools', 'def test_returns_twenty_tools')
content = content.replace('"""Test that tools have expected names."""\n    def test_tool_names', 'def test_tool_names')

# Do it properly using a small python script
lines = content.split('\n')
new_lines = []

for line in lines:
    new_lines.append(line)
    if "async def test_" in line or "def test_" in line:
        spaces = len(line) - len(line.lstrip())
        new_lines.append(" " * spaces + '    """Test method."""')

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write('\n'.join(new_lines))
