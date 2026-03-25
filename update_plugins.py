import re

with open("backend/app/api/plugins.py", "r") as f:
    content = f.read()

old_caller = """    oauth_cfg = manifest.oauth
    client_name = oauth_cfg.client_name if oauth_cfg else "Omni Hub"
    scopes = oauth_cfg.scopes if oauth_cfg else []
    redirect_uri = oauth_cfg.redirect_uri if oauth_cfg and oauth_cfg.redirect_uri else ""

    try:
        oauth = get_oauth_service()
        auth_url = await oauth.start_oauth_flow(
            plugin_id=plugin_id,
            user_id=user.uid,
            mcp_server_url=manifest.url,
            client_name=client_name,
            scopes=scopes,
            redirect_uri=redirect_uri,
        )"""

new_caller = """    try:
        oauth = get_oauth_service()
        auth_url = await oauth.start_oauth_flow(
            plugin_id=plugin_id,
            user_id=user.uid,
            mcp_server_url=manifest.url,
            oauth_config=manifest.oauth,
        )"""

content = content.replace(old_caller, new_caller)

with open("backend/app/api/plugins.py", "w") as f:
    f.write(content)
