"""Test Brave Search MCP Server connection.

Tests that the Brave Search MCP stdio server can start, connect,
discover tools, and optionally perform a live web search.

Usage:
    # Set your Brave API key (get from https://api.search.brave.com/app/keys)
    export BRAVE_API_KEY=BSAxxxxx

    # Run the test
    cd backend
    uv run python scripts/test_brave_mcp.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────
API_KEY = os.environ.get("BRAVE_API_KEY", "")
PACKAGE = "@modelcontextprotocol/server-brave-search"

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
    print(f"{BOLD}  Brave Search MCP Server Test{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Package : {PACKAGE}")
    print(f"  API Key : {'***' + API_KEY[-4:] if API_KEY else '(not set)'}")
    print()

    if not API_KEY:
        fail("BRAVE_API_KEY not set.")
        print(f"\n  Set it with:")
        print(f"    export BRAVE_API_KEY=BSAxxxxx")
        print(f"  Get one at: https://api.search.brave.com/app/keys\n")
        sys.exit(1)

    # ── Test 1: MCP connection ──────────────────────────────────────
    print(f"  {BOLD}Test 1: Connect to MCP server & discover tools{RESET}")
    toolset = None
    tools = []
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
        from mcp.client.stdio import StdioServerParameters

        params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", PACKAGE],
                env={"BRAVE_API_KEY": API_KEY},
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

    # ── Test 2: Live search ─────────────────────────────────────────
    print(f"\n  {BOLD}Test 2: Live API call — brave_web_search{RESET}")
    try:
        search_tool = None
        for t in tools:
            if getattr(t, "name", "") == "brave_web_search":
                search_tool = t
                break

        if search_tool is None:
            warn("brave_web_search tool not found.")
        else:
            from google.adk.tools.mcp_tool.mcp_tool import McpTool

            if isinstance(search_tool, McpTool):
                result = await search_tool.run_async(
                    args={"query": "Model Context Protocol MCP servers"},
                    tool_context=None,
                )
                if result and "error" not in str(result).lower():
                    ok("brave_web_search returned results.")
                    info(f"  Response preview: {str(result)[:200]}...")
                else:
                    fail(f"brave_web_search returned error: {result}")
            else:
                warn("Tool is not McpTool type, skipping live call.")

    except Exception as exc:
        fail(f"Live search failed: {exc}")

    # ── Cleanup ─────────────────────────────────────────────────────
    if toolset:
        try:
            await toolset.close()
        except Exception:
            pass

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"  {GREEN}Brave Search MCP test complete!{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
