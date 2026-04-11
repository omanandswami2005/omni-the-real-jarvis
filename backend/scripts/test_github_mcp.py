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
# New official GitHub MCP server (Go binary), replaces deprecated @modelcontextprotocol/server-github
BINARY = "github-mcp-server.exe"
BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "bin")

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
    print(f"  Binary  : {BINARY}")
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

        # Resolve binary path — check backend/bin/ first, then PATH
        binary_path = os.path.join(BIN_DIR, BINARY)
        if not os.path.isfile(binary_path):
            binary_path = BINARY  # fall back to PATH

        params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command=binary_path,
                args=["stdio"],
                env={"GITHUB_PERSONAL_ACCESS_TOKEN": TOKEN},
            ),
            timeout=60.0,
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
                result_str = str(result)
                # Check for actual error — not just the word "error" in field names
                is_error = (
                    result is None
                    or (isinstance(result, dict) and result.get("isError"))
                    or '"isError": true' in result_str.lower()
                    or '"isError":true' in result_str.lower()
                )
                if result and not is_error:
                    ok(f"search_repositories returned results successfully.")
                    info(f"  Response preview: {result_str[:200]}...")
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
