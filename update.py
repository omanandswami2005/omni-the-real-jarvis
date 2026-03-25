import re

with open("backend/app/services/oauth_service.py", "r") as f:
    content = f.read()

# Add import
import_stmt = "from app.models.plugin import OAuthConfig\n"
content = content.replace("from app.services import secret_service\n", "from app.models.plugin import OAuthConfig\nfrom app.services import secret_service\n")

# Replace signature
old_sig = """    async def start_oauth_flow(
        self,
        plugin_id: str,
        user_id: str,
        mcp_server_url: str,
        client_name: str = "Omni Hub",
        scopes: list[str] | None = None,
        redirect_uri: str = "",
    ) -> str:"""

new_sig = """    async def start_oauth_flow(
        self,
        plugin_id: str,
        user_id: str,
        mcp_server_url: str,
        oauth_config: OAuthConfig | None = None,
    ) -> str:"""

content = content.replace(old_sig, new_sig)

# Replace local variables
old_vars = """        \"\"\"Begin OAuth authorization. Returns the authorization URL to redirect the user to.\"\"\"
        if not redirect_uri:"""

new_vars = """        \"\"\"Begin OAuth authorization. Returns the authorization URL to redirect the user to.\"\"\"
        client_name = oauth_config.client_name if oauth_config else "Omni Hub"
        scopes = oauth_config.scopes if oauth_config else []
        redirect_uri = oauth_config.redirect_uri if oauth_config and oauth_config.redirect_uri else ""

        if not redirect_uri:"""

content = content.replace(old_vars, new_vars)

with open("backend/app/services/oauth_service.py", "w") as f:
    f.write(content)
