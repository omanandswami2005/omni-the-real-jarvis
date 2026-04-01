import base64

with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content = f.read()

# 1. Fix tools length
content = content.replace("assert len(tools) >= 20", "assert len(tools) == 27")

# 2. Fix screenshot test
search_screenshot = """    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_returns_image(self, mock_get_svc):
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_screenshot(user_id="u1")
        assert "message" in result
        svc.screenshot.assert_awaited_once_with("u1")"""

replace_screenshot = """    @pytest.mark.asyncio
    @patch(_SVC)
    @patch("app.tools.desktop_tools._queue_screenshot")
    async def test_returns_image(self, mock_queue, mock_get_svc):
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_screenshot(user_id="u1")
        assert "message" in result
        svc.screenshot.assert_awaited_once_with("u1")
        mock_queue.assert_called_once_with("u1", "iVBORyBmYWtl", description="Desktop screenshot")"""
content = content.replace(search_screenshot, replace_screenshot)

# 3. Fix clipboard test pipefail
search_cmd = """        expected_cmd = f"echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null"
        svc.run_command.assert_awaited_once_with("u1", expected_cmd)"""

replace_cmd = """        expected_cmd = (
            f"set -o pipefail; echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || "
            f"{{ set -o pipefail; echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null; }}"
        )
        svc.run_command.assert_awaited_once_with("u1", expected_cmd)"""
content = content.replace(search_cmd, replace_cmd)

# 4. Docstrings
lines = content.split('\n')
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if "def _mock_svc():" in line:
        new_lines.append('    """Mock desktop service."""')
    elif line.startswith("class Test"):
        new_lines.append('    """Tests."""')
    elif "def test_" in line:
        spaces = len(line) - len(line.lstrip())
        # Look ahead to check if next non-empty, non-comment line already has a docstring
        has_docstring = False
        for j in range(i + 1, len(lines)):
            next_line = lines[j].strip()
            if next_line and not next_line.startswith('#'):
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    has_docstring = True
                break
        if not has_docstring:
            new_lines.append(" " * (spaces + 4) + '"""Test case."""')

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write('\n'.join(new_lines))