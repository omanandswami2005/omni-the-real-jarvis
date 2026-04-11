"""Native plugin — Google Drive (per-user OAuth).

Each user connects their own Google account via OAuth 2.0.  Tools then
operate on *that user's* Drive files using their personal access token.

Token is automatically injected via tool_context (same pattern as Calendar).

Scopes: https://www.googleapis.com/auth/drive.readonly
"""

from __future__ import annotations

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from app.models.plugin import (
    PluginCategory,
    PluginKind,
    PluginManifest,
    ToolSummary,
)

GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

_PLUGIN_ID = "google-drive"

MANIFEST = PluginManifest(
    id=_PLUGIN_ID,
    name="Google Drive",
    description="Search and read files from your Google Drive. "
    "Each user connects their own Google account via OAuth.",
    version="0.1.0",
    author="Omni Hub Team",
    category=PluginCategory.PRODUCTIVITY,
    kind=PluginKind.NATIVE,
    icon="google-drive",
    tags=["knowledge", "gcp", "files"],
    module="app.plugins.google_drive_plugin",
    factory="get_tools",
    requires_auth=True,
    google_oauth_scopes=GOOGLE_DRIVE_SCOPES,
    tools_summary=[
        ToolSummary(
            name="search_drive_files",
            description="Search for files in the user's Google Drive",
        ),
        ToolSummary(
            name="read_drive_file",
            description="Read the text content of a file from Google Drive",
        ),
        ToolSummary(
            name="list_drive_files",
            description="List recent files in the user's Google Drive",
        ),
    ],
)

_API = "https://www.googleapis.com/drive/v3"


# ---------------------------------------------------------------------------
# Token helper (same pattern as google_calendar_plugin)
# ---------------------------------------------------------------------------

async def _get_token(tool_context: ToolContext | None) -> str | None:
    """Get the Google OAuth access token from the session context."""
    from app.utils.logging import get_logger
    _log = get_logger(__name__)

    if tool_context is None:
        _log.warning("drive_get_token_no_context")
        return None
    user_id = getattr(tool_context, "user_id", None)
    if not user_id:
        _log.warning("drive_get_token_no_user_id")
        return None
    from app.services.google_oauth_service import get_google_oauth_service
    goauth = get_google_oauth_service()
    token = await goauth.get_valid_token(user_id, _PLUGIN_ID)
    if not token:
        _log.warning("drive_get_token_failed", user_id=user_id, plugin_id=_PLUGIN_ID,
                      has_tokens=goauth.has_tokens(user_id, _PLUGIN_ID))
    else:
        _log.debug("drive_get_token_ok", user_id=user_id)
    return token


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def search_drive_files(
    query: str,
    max_results: int = 10,
    tool_context: ToolContext | None = None,
) -> dict:
    """Search for files in the user's Google Drive.

    Args:
        query: Search query (supports Google Drive search syntax).
        max_results: Maximum number of results to return (1-50).

    Returns:
        A dict with matching files.
    """
    import httpx

    access_token = await _get_token(tool_context)
    if not access_token:
        return {"error": "Google Drive token unavailable. Please connect your Google account on the Integrations page."}

    max_results = max(1, min(50, max_results))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_API}/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "q": f"fullText contains '{query}' and trashed = false",
                "pageSize": str(max_results),
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink,size)",
                "orderBy": "modifiedTime desc",
            },
        )
        if resp.status_code == 401:
            return {"error": "Token expired or revoked. Please reconnect your Google account."}
        resp.raise_for_status()
        data = resp.json()

    files = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "type": f.get("mimeType", ""),
            "modified": f.get("modifiedTime", ""),
            "link": f.get("webViewLink", ""),
            "size": f.get("size", ""),
        }
        for f in data.get("files", [])
    ]
    return {"files": files, "count": len(files)}


async def read_drive_file(
    file_id: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """Read the text content of a file from Google Drive.

    Supports Google Docs (exported as plain text) and plain text files.

    Args:
        file_id: The ID of the file to read.

    Returns:
        A dict with the file name and content.
    """
    import httpx

    access_token = await _get_token(tool_context)
    if not access_token:
        return {"error": "Google Drive token unavailable. Please connect your Google account on the Integrations page."}

    async with httpx.AsyncClient(timeout=15) as client:
        # Get file metadata
        meta_resp = await client.get(
            f"{_API}/files/{file_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "id,name,mimeType"},
        )
        if meta_resp.status_code == 401:
            return {"error": "Token expired or revoked. Please reconnect your Google account."}
        if meta_resp.status_code == 404:
            return {"error": f"File '{file_id}' not found."}
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        mime = meta.get("mimeType", "")

        # Google Docs → export as plain text
        if mime == "application/vnd.google-apps.document":
            resp = await client.get(
                f"{_API}/files/{file_id}/export",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"mimeType": "text/plain"},
            )
        elif mime == "application/vnd.google-apps.spreadsheet":
            resp = await client.get(
                f"{_API}/files/{file_id}/export",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"mimeType": "text/csv"},
            )
        else:
            # Regular file — download content
            resp = await client.get(
                f"{_API}/files/{file_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"alt": "media"},
            )

        if resp.status_code == 401:
            return {"error": "Token expired or revoked. Please reconnect your Google account."}
        resp.raise_for_status()

        # Limit content to 50KB to avoid blowing up context
        content = resp.text[:50_000]
        truncated = len(resp.text) > 50_000

    return {
        "file_id": file_id,
        "name": meta.get("name", ""),
        "mime_type": mime,
        "content": content,
        "truncated": truncated,
    }


async def list_drive_files(
    max_results: int = 20,
    tool_context: ToolContext | None = None,
) -> dict:
    """List recent files in the user's Google Drive.

    Args:
        max_results: Maximum number of files to return (1-100).

    Returns:
        A dict with recent files.
    """
    import httpx

    access_token = await _get_token(tool_context)
    if not access_token:
        return {"error": "Google Drive token unavailable. Please connect your Google account on the Integrations page."}

    max_results = max(1, min(100, max_results))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_API}/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "pageSize": str(max_results),
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink,size)",
                "orderBy": "modifiedTime desc",
                "q": "trashed = false",
            },
        )
        if resp.status_code == 401:
            return {"error": "Token expired or revoked. Please reconnect your Google account."}
        resp.raise_for_status()
        data = resp.json()

    files = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "type": f.get("mimeType", ""),
            "modified": f.get("modifiedTime", ""),
            "link": f.get("webViewLink", ""),
        }
        for f in data.get("files", [])
    ]
    return {"files": files, "count": len(files)}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_tools() -> list[FunctionTool]:
    return [
        FunctionTool(search_drive_files),
        FunctionTool(read_drive_file),
        FunctionTool(list_drive_files),
    ]
