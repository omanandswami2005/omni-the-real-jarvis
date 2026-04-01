with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content = f.read()

content = content.replace('"iVBORw0KGgo="', '"iVBORyBmYWtl"')

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content)
