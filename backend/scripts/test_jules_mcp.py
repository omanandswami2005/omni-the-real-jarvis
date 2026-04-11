"""Test Jules — both the official MCP server and the native REST plugin.

Tests:
  1. Official MCP server (@google/jules-mcp) — connects and discovers tools
  2. Native REST plugin — calls the Jules API directly

Usage:
    # Set your Jules API key (get from https://jules.google.com/settings#api)
    export JULES_API_KEY=your_key_here

    # Run the test
    cd backend
    uv run python scripts/test_jules_mcp.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────
API_KEY = os.environ.get("JULES_API_KEY", "")
MCP_PACKAGE = "@google/jules-mcp"
BASE_URL = "https://jules.googleapis.com/v1alpha"

# ── ANSI helpers ────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✔ PASS{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✘ FAIL{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠ SKIP{RESET}  {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}ℹ{RESET}  {msg}")


# ─────────────────────────────────────────────────────────────────────
# Test 1: Official MCP Server
# ─────────────────────────────────────────────────────────────────────
async def test_jules_mcp() -> bool:
    """Connect to @google/jules-mcp and discover tools."""
    print(f"\n  {BOLD}Test 1: Jules MCP Server (@google/jules-mcp){RESET}")

    if not API_KEY:
        warn("JULES_API_KEY not set — skipping MCP test.")
        return False

    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
        from mcp.client.stdio import StdioServerParameters

        params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", MCP_PACKAGE],
                env={"JULES_API_KEY": API_KEY},
            ),
            timeout=60.0,  # npx cold-start can be slow
        )

        toolset = McpToolset(connection_params=params)
        tools = await toolset.get_tools()
        tool_names = [getattr(t, "name", str(t)) for t in tools]

        if tools:
            ok(f"MCP connected! Found {len(tools)} tools.")
            for name in sorted(tool_names):
                info(f"  → {name}")
            await toolset.close()
            return True
        else:
            fail("MCP connected but no tools returned.")
            await toolset.close()
            return False

    except Exception as exc:
        fail(f"MCP connection failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────
# Test 2: Native REST Plugin — list sources
# ─────────────────────────────────────────────────────────────────────
async def test_jules_rest_sources() -> bool:
    """Call the Jules REST API to list connected sources."""
    print(f"\n  {BOLD}Test 2: Jules REST API — list sources{RESET}")

    if not API_KEY:
        warn("JULES_API_KEY not set — skipping REST test.")
        return False

    import httpx

    headers = {"x-goog-api-key": API_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/sources", headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                sources = data.get("sources", [])
                ok(f"Listed {len(sources)} connected sources.")
                for s in sources:
                    gh = s.get("githubRepo", {})
                    info(f"  → {gh.get('owner', '?')}/{gh.get('repo', '?')}")
                return True
            elif resp.status_code == 401:
                fail("Invalid Jules API key (401 Unauthorized).")
                info("Get your key at: https://jules.google.com/settings#api")
                return False
            elif resp.status_code == 403:
                fail("Access denied (403 Forbidden). Check API key permissions.")
                return False
            else:
                fail(f"Unexpected status {resp.status_code}: {resp.text[:200]}")
                return False

    except httpx.ConnectError:
        fail(f"Cannot reach {BASE_URL} — check network/firewall.")
        return False
    except Exception as exc:
        fail(f"REST call failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────
# Test 3: Native REST Plugin — list sessions
# ─────────────────────────────────────────────────────────────────────
async def test_jules_rest_sessions() -> bool:
    """Call the Jules REST API to list sessions."""
    print(f"\n  {BOLD}Test 3: Jules REST API — list sessions{RESET}")

    if not API_KEY:
        warn("JULES_API_KEY not set — skipping.")
        return False

    import httpx

    headers = {"x-goog-api-key": API_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/sessions",
                headers=headers,
                params={"pageSize": "5"},
            )

            if resp.status_code == 200:
                data = resp.json()
                sessions = data.get("sessions", [])
                ok(f"Listed {len(sessions)} sessions.")
                for s in sessions[:3]:
                    info(f"  → [{s.get('state', '?')}] {s.get('title', '(no title)')}")
                return True
            elif resp.status_code == 401:
                fail("Invalid Jules API key.")
                return False
            else:
                fail(f"Unexpected status {resp.status_code}: {resp.text[:200]}")
                return False

    except Exception as exc:
        fail(f"REST call failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Jules Plugin Test (MCP + REST){RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  API Key : {'***' + API_KEY[-4:] if API_KEY else '(not set)'}")
    print(f"  MCP Pkg : {MCP_PACKAGE}")
    print(f"  REST URL: {BASE_URL}")

    if not API_KEY:
        fail("JULES_API_KEY not set.")
        print(f"\n  Set it with:")
        print(f"    export JULES_API_KEY=your_key_here")
        print(f"  Get one at: https://jules.google.com/settings#api\n")
        sys.exit(1)

    results = {}
    results["mcp"] = await test_jules_mcp()
    results["sources"] = await test_jules_rest_sources()
    results["sessions"] = await test_jules_rest_sessions()

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{BOLD}{'='*60}{RESET}")
    color = GREEN if passed == total else (YELLOW if passed > 0 else RED)
    print(f"  {color}{passed}/{total} tests passed{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
