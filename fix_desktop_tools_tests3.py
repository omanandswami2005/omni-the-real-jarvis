with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content = f.read()

search_cmd = """        expected_cmd = f"echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null"
        svc.run_command.assert_awaited_once_with("u1", expected_cmd)"""

replace_cmd = """        expected_cmd = (
            f"set -o pipefail; echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || "
            f"{{ set -o pipefail; echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null; }}"
        )
        svc.run_command.assert_awaited_once_with("u1", expected_cmd)"""
content = content.replace(search_cmd, replace_cmd)

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content)
