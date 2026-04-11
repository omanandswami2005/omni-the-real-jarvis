"""Test GitHub MCP Server connection.

Tests that the GitHub MCP stdio server can start, connect, and return tools.
Optionally runs a live search if GITHUB_PERSONAL_ACCESS_TOKEN is set.

Usage:
    # Set your token (get from https://github.com/settings/tokens)
    export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxxx

    # Run the test
    cd backend
    uv run python scripts/test_github_mcp.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Allow running from backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
PACKAGE = "@modelcontextprotocol/server-github"

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


async def main() -> None:
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  GitHub MCP Server Test{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Package : {PACKAGE}")
    print(f"  Token   : {'***' + TOKEN[-4:] if TOKEN else '(not set)'}")
    print()

    if not TOKEN:
        fail("GITHUB_PERSONAL_ACCESS_TOKEN not set.")
        print(f"\n  Set it with:")
        print(f"    export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxxx")
        print(f"  Get one at: https://github.com/settings/tokens\n")
        sys.exit(1)

    # ── Test 1: MCP connection via ADK McpToolset ───────────────────
    print(f"  {BOLD}Test 1: Connect to MCP server & discover tools{RESET}")
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
        from mcp.client.stdio import StdioServerParameters

        params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", PACKAGE],
                env={"GITHUB_PERSONAL_ACCESS_TOKEN": TOKEN},
            ),
            timeout=60.0,  # npx cold-start can be slow
        )

        toolset = McpToolset(connection_params=params)
        tools = await toolset.get_tools()
        tool_names = [getattr(t, "name", str(t)) for t in tools]

        if tools:
            ok(f"Connected! Found {len(tools)} tools.")
            for name in sorted(tool_names):
                info(f"  → {name}")
        else:
            fail("Connected but no tools returned.")
            await toolset.close()
            sys.exit(1)

    except Exception as exc:
        fail(f"MCP connection failed: {exc}")
        sys.exit(1)

    # ── Test 2: Live API call — search repos ────────────────────────
    print(f"\n  {BOLD}Test 2: Live API call — search_repositories{RESET}")
    try:
        # Find the search tool
        search_tool = None
        for t in tools:
            if getattr(t, "name", "") == "search_repositories":
                search_tool = t
                break

        if search_tool is None:
            warn("search_repositories tool not found in discovered tools.")
        else:
            # Call the tool directly via MCP
            from google.adk.tools.mcp_tool.mcp_tool import McpTool

            if isinstance(search_tool, McpTool):
                result = await search_tool.run_async(
                    args={"query": "modelcontextprotocol"},
                    tool_context=None,
                )
                if result and "error" not in str(result).lower():
                    ok(f"search_repositories returned results successfully.")
                    info(f"  Response preview: {str(result)[:200]}...")
                else:
                    fail(f"search_repositories returned error: {result}")
            else:
                warn("Tool is not McpTool type, skipping live call.")

    except Exception as exc:
        fail(f"Live API call failed: {exc}")

    # ── Cleanup ─────────────────────────────────────────────────────
    try:
        await toolset.close()
    except Exception:
        pass

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"  {GREEN}GitHub MCP test complete!{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
