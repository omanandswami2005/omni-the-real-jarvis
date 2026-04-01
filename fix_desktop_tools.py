with open("backend/app/tools/desktop_tools.py", "r") as f:
    content = f.read()

# Fix desktop_clipboard_write
search_clipboard = """    b64_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    await svc.run_command(
        user_id,
        f"echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null"
    )
    return {"copied": True, "length": len(text)}"""

replace_clipboard = """    b64_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    cmd = (
        f"set -o pipefail; echo '{b64_text}' | base64 -d | xclip -selection clipboard 2>/dev/null || "
        f"{{ set -o pipefail; echo '{b64_text}' | base64 -d | xsel --clipboard --input 2>/dev/null; }}"
    )
    result = await svc.run_command(user_id, cmd)
    if result.get("exit_code", -1) != 0:
        return {"copied": False, "length": len(text)}
    return {"copied": True, "length": len(text)}"""

content = content.replace(search_clipboard, replace_clipboard)

# Add missing docstrings
# Let's just find `def ` without `"""` and add docstrings.
# Actually, I can use a simpler approach. I'll read the file and insert docstrings where missing.

with open("backend/app/tools/desktop_tools.py", "w") as f:
    f.write(content)