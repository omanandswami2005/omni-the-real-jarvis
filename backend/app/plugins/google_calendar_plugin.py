"""Native plugin — Google Calendar (per-user OAuth).

Each user connects their own Google account via OAuth 2.0.  Tools then
operate on *that user's* calendar using their personal access token.

Scopes: https://www.googleapis.com/auth/calendar
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from app.models.plugin import (
    PluginCategory,
    PluginKind,
    PluginManifest,
    ToolSummary,
)

GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

MANIFEST = PluginManifest(
    id="google-calendar",
    name="Google Calendar",
    description="Read, create, and manage events on your Google Calendar. "
    "Interpret relative scheduling from the current time and default to "
    "IST (Asia/Kolkata) unless the user specifies another timezone. "
    "Each user connects their own Google account via OAuth.",
    version="0.1.0",
    author="Omni Hub Team",
    category=PluginCategory.PRODUCTIVITY,
    kind=PluginKind.NATIVE,
    icon="google-calendar",
    tags=["productivity", "gcp", "calendar", "communication"],
    module="app.plugins.google_calendar_plugin",
    factory="get_tools",
    requires_auth=True,
    google_oauth_scopes=GOOGLE_CALENDAR_SCOPES,
    tools_summary=[
        ToolSummary(
            name="list_calendar_events",
            description="List upcoming events from now onward in the user's Google Calendar",
        ),
        ToolSummary(
            name="create_calendar_event",
            description="Create a new event on the user's Google Calendar (default timezone: IST)",
        ),
        ToolSummary(
            name="delete_calendar_event",
            description="Delete an event from the user's Google Calendar",
        ),
    ],
)

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

_API = "https://www.googleapis.com/calendar/v3"
_PLUGIN_ID = "google-calendar"
_DEFAULT_TIMEZONE = "Asia/Kolkata"


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse ISO-like datetime strings, including trailing Z."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_datetime_field(raw_value: str, fallback_tz: str) -> dict | None:
    """Build Google Calendar dateTime payload with timezone fallback."""
    parsed = _parse_iso_datetime(raw_value)
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        return {"dateTime": parsed.isoformat()}
    return {"dateTime": parsed.isoformat(), "timeZone": fallback_tz}


def _normalize_recurrence(
    recurrence: list[str] | str | None,
    recurrence_rule: str,
) -> list[str]:
    """Normalize recurrence inputs to Google Calendar recurrence lines."""
    lines: list[str] = []

    if isinstance(recurrence, list):
        lines.extend(str(v).strip() for v in recurrence if str(v).strip())
    elif isinstance(recurrence, str) and recurrence.strip():
        lines.append(recurrence.strip())

    if recurrence_rule.strip():
        lines.append(recurrence_rule.strip())

    normalized: list[str] = []
    for line in lines:
        upper = line.upper()
        if upper.startswith("RRULE:") or upper.startswith("EXDATE:") or upper.startswith("RDATE:"):
            normalized.append(line)
        elif "FREQ=" in upper:
            normalized.append(f"RRULE:{line}")
        else:
            normalized.append(line)
    return normalized


async def _get_token(tool_context: ToolContext | None) -> str | None:
    """Get the Google OAuth access token from the session context."""
    from app.utils.logging import get_logger
    _log = get_logger(__name__)

    if tool_context is None:
        _log.warning("calendar_get_token_no_context")
        return None
    user_id = getattr(tool_context, "user_id", None)
    if not user_id:
        _log.warning("calendar_get_token_no_user_id")
        return None
    from app.services.google_oauth_service import get_google_oauth_service
    goauth = get_google_oauth_service()
    token = await goauth.get_valid_token(user_id, _PLUGIN_ID)
    if not token:
        _log.warning("calendar_get_token_failed", user_id=user_id, plugin_id=_PLUGIN_ID,
                      has_tokens=goauth.has_tokens(user_id, _PLUGIN_ID))
    else:
        _log.debug("calendar_get_token_ok", user_id=user_id)
    return token


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def list_calendar_events(
    max_results: int = 10,
    tool_context: ToolContext | None = None,
) -> dict:
    """List upcoming events from the user's Google Calendar.

    Uses the current time as the reference point for what counts as "upcoming".

    Args:
        max_results: Maximum number of events to return (1-50).

    Returns:
        A dict with the list of upcoming events.
    """
    import httpx

    from app.utils.logging import get_logger
    _log = get_logger(__name__)

    try:
        access_token = await _get_token(tool_context)
        if not access_token:
            return {"error": "Google Calendar token unavailable. The token refresh may have failed. Ask the user to reconnect Google Calendar on the Integrations page."}

        max_results = max(1, min(50, max_results))
        now = datetime.now(UTC).isoformat()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_API}/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "maxResults": str(max_results),
                    "timeMin": now,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            if resp.status_code == 401:
                return {"error": "Token expired or revoked. Please reconnect your Google account."}
            resp.raise_for_status()
            data = resp.json()

        events = []
        for item in data.get("items", []):
            start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date", "")
            end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date", "")
            events.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary", "(No title)"),
                    "start": start,
                    "end": end,
                    "location": item.get("location", ""),
                    "description": item.get("description", "")[:200],
                }
            )

        return {"events": events, "count": len(events)}
    except Exception as exc:
        _log.exception("list_calendar_events_failed", user_id=getattr(tool_context, "user_id", None))
        return {"error": f"Calendar API error: {exc}"}


async def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str = "",
    description: str = "",
    location: str = "",
    timezone: str = "Asia/Kolkata",
    recurrence_rule: str = "",
    recurrence: list[str] | str | None = None,
    duration_minutes: int = 30,
    tool_context: ToolContext | None = None,
) -> dict:
    """Create a new event on the user's Google Calendar.

    Args:
        summary: Title of the event.
        start_time: Start time in ISO 8601 format (e.g. 2026-03-15T10:00:00-05:00).
            If the user asked with relative terms (e.g. "tomorrow 9 AM"), resolve them
            against the current time before calling this tool.
        end_time: End time in ISO 8601 format. If omitted, defaults to start + duration_minutes.
        description: Optional description.
        location: Optional location.
        timezone: IANA timezone for naive datetimes. Defaults to "Asia/Kolkata" (IST)
            when omitted.
        recurrence_rule: Optional recurrence rule. Accepts both
            "RRULE:FREQ=WEEKLY;BYDAY=SA,SU" and "FREQ=WEEKLY;BYDAY=SA,SU".
        recurrence: Optional recurrence lines (list or string), merged with recurrence_rule.
        duration_minutes: Default duration used when end_time is omitted.

    Returns:
        A dict with the created event details.
    """
    import httpx

    access_token = await _get_token(tool_context)
    if not access_token:
        return {"error": "Google Calendar token unavailable. The token refresh may have failed. Ask the user to reconnect Google Calendar on the Integrations page."}

    tz_name = timezone.strip() or _DEFAULT_TIMEZONE

    if not end_time.strip():
        start_dt = _parse_iso_datetime(start_time)
        if start_dt is None:
            return {
                "error": "Invalid start_time. Use ISO 8601 format, e.g. 2026-04-17T07:10:00 or 2026-04-17T07:10:00-04:00."
            }
        safe_duration = max(1, min(1440, int(duration_minutes)))
        end_time = (start_dt + timedelta(minutes=safe_duration)).isoformat()

    start_field = _build_datetime_field(start_time, tz_name)
    end_field = _build_datetime_field(end_time, tz_name)
    if start_field is None or end_field is None:
        return {
            "error": "Invalid start_time or end_time. Use ISO 8601 format, e.g. 2026-04-17T07:10:00 or 2026-04-17T07:40:00-04:00."
        }

    recurrence_lines = _normalize_recurrence(recurrence, recurrence_rule)

    body: dict = {
        "summary": summary,
        "start": start_field,
        "end": end_field,
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if recurrence_lines:
        body["recurrence"] = recurrence_lines

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_API}/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        if resp.status_code == 401:
            return {"error": "Token expired or revoked. Please reconnect your Google account."}
        if resp.status_code not in (200, 201):
            detail = "Unknown calendar API error"
            with contextlib.suppress(Exception):
                payload = resp.json() or {}
                err = payload.get("error", {}) if isinstance(payload, dict) else {}
                detail = err.get("message", detail) if isinstance(err, dict) else detail
            hint = (
                "For recurring events, provide RRULE like 'FREQ=WEEKLY;BYDAY=SA,SU'. "
                "For naive datetimes, provide timezone or include offset. "
                "If omitted, IST (Asia/Kolkata) is used by default."
            )
            return {
                "error": f"Google Calendar API error ({resp.status_code}): {detail}",
                "hint": hint,
                "request_body": body,
            }

        event = resp.json()

    return {
        "success": True,
        "event_id": event.get("id"),
        "summary": event.get("summary"),
        "link": event.get("htmlLink"),
        "start": event.get("start", {}),
        "end": event.get("end", {}),
        "recurrence": event.get("recurrence", []),
    }


async def delete_calendar_event(
    event_id: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """Delete an event from the user's Google Calendar.

    Args:
        event_id: The ID of the event to delete.

    Returns:
        A dict with the deletion status.
    """
    import httpx

    access_token = await _get_token(tool_context)
    if not access_token:
        return {"error": "Google Calendar token unavailable. The token refresh may have failed. Ask the user to reconnect Google Calendar on the Integrations page."}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{_API}/calendars/primary/events/{event_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code == 401:
            return {"error": "Token expired or revoked. Please reconnect your Google account."}
        if resp.status_code == 404:
            return {"error": f"Event '{event_id}' not found."}
        resp.raise_for_status()

    return {"success": True, "message": f"Event '{event_id}' deleted."}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_tools() -> list[FunctionTool]:
    return [
        FunctionTool(list_calendar_events),
        FunctionTool(create_calendar_event),
        FunctionTool(delete_calendar_event),
    ]
