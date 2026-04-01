with open("backend/tests/test_tools/test_desktop_tools.py", "r") as f:
    content = f.read()

# Update exact tools count 27
search_tools = """class TestGetDesktopTools:
    def test_returns_twenty_tools(self):
        tools = get_desktop_tools()
        assert len(tools) >= 20"""

replace_tools = """class TestGetDesktopTools:
    def test_returns_twenty_tools(self):
        tools = get_desktop_tools()
        assert len(tools) == 27"""

content = content.replace(search_tools, replace_tools)

# Update screenshot test to check queue
# Wait, let's look at test_returns_image
search_screenshot = """    @pytest.mark.asyncio
    @patch(_SVC)
    async def test_returns_image(self, mock_get_svc):
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_screenshot(user_id="u1")
        assert "message" in result
        svc.screenshot.assert_awaited_once_with("u1")"""

import base64
expected_b64 = base64.b64encode(b"\x89PNG fake").decode()

replace_screenshot = f"""    @pytest.mark.asyncio
    @patch(_SVC)
    @patch("app.tools.desktop_tools._queue_screenshot")
    async def test_returns_image(self, mock_queue, mock_get_svc):
        svc = _mock_svc()
        mock_get_svc.return_value = svc
        result = await desktop_screenshot(user_id="u1")
        assert "message" in result
        svc.screenshot.assert_awaited_once_with("u1")
        # Ensure it enqueues the base64 image
        mock_queue.assert_called_once_with("u1", "{expected_b64}", description="Desktop screenshot")"""

content = content.replace(search_screenshot, replace_screenshot)

with open("backend/tests/test_tools/test_desktop_tools.py", "w") as f:
    f.write(content)