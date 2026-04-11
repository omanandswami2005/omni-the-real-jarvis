"""Test all MCP servers — interactive runner.

Discovers every MCP config in app/mcps/*.json and every native plugin
in app/plugins/*.py, then lets you test each one individually.

For stdio/http MCPs: spawns the MCP process, connects, discovers tools.
For native plugins: imports the module and calls the factory function.

Usage:
    cd backend
    uv run python scripts/test_all_mcps.py                  # interactive menu
    uv run python scripts/test_all_mcps.py --mcp github     # test one MCP
    uv run python scripts/test_all_mcps.py --mcp jules      # test Jules MCP
    uv run python scripts/test_all_mcps.py --native jules    # test native Jules plugin
    uv run python scripts/test_all_mcps.py --list            # list all plugins

API keys should be set in your .env or as environment variables.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# ── ANSI helpers ────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✔ PASS{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✘ FAIL{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠ SKIP{RESET}  {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}ℹ{RESET}  {msg}")


def header(msg: str) -> None:
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"  {BOLD}{msg}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")


# ── Discovery ───────────────────────────────────────────────────────

MCPS_DIR = Path(__file__).parent.parent / "app" / "mcps"
PLUGINS_DIR = Path(__file__).parent.parent / "app" / "plugins"


def discover_mcps() -> list[dict]:
    """Load all MCP JSON configs."""
    mcps = []
    for path in sorted(MCPS_DIR.glob("*.json")):
        if path.name.startswith("_") or path.name == "TEMPLATE.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_file"] = path.name
            mcps.append(data)
        except Exception as exc:
            print(f"  {RED}Error loading {path.name}: {exc}{RESET}")
    return mcps


def discover_native_plugins() -> list[dict]:
    """Discover native Python plugins with MANIFEST."""
    plugins = []
    for path in sorted(PLUGINS_DIR.glob("*.py")):
        if path.name.startswith("_") or path.name == "TEMPLATE.py":
            continue
        module_name = f"app.plugins.{path.stem}"
        try:
            mod = importlib.import_module(module_name)
            manifest = getattr(mod, "MANIFEST", None)
            if manifest:
                plugins.append({
                    "id": manifest.id,
                    "name": manifest.name,
                    "kind": str(manifest.kind),
                    "module": module_name,
                    "factory": manifest.factory,
                    "env_keys": manifest.env_keys,
                    "requires_auth": manifest.requires_auth,
                    "_file": path.name,
                })
        except Exception as exc:
            print(f"  {RED}Error importing {module_name}: {exc}{RESET}")
    return plugins


# ── MCP Tests ───────────────────────────────────────────────────────


def _resolve_env(mcp: dict) -> dict[str, str] | None:
    """Resolve environment variables for an MCP. Returns None if missing required keys."""
    env = {}
    for key in mcp.get("env_keys", []):
        value = os.environ.get(key, "")
        if not value:
            return None
        env[key] = value
    return env


async def test_mcp_stdio(mcp: dict) -> bool:
    """Test a stdio MCP server by connecting and discovering tools."""
    mcp_id = mcp["id"]
    env = _resolve_env(mcp)

    if mcp.get("requires_auth", False) and env is None:
        missing = [k for k in mcp.get("env_keys", []) if not os.environ.get(k)]
        warn(f"Missing env: {', '.join(missing)}")
        return False

    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
        from mcp.client.stdio import StdioServerParameters

        params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command=mcp["command"],
                args=mcp.get("args", []),
                env=env or None,
            ),
            timeout=60.0,  # npx cold-start can be slow
        )

        toolset = McpToolset(connection_params=params)
        tools = await asyncio.wait_for(toolset.get_tools(), timeout=30)
        tool_names = sorted(getattr(t, "name", str(t)) for t in tools)

        if tools:
            ok(f"[{mcp_id}] Connected — {len(tools)} tools discovered")
            for name in tool_names:
                info(f"  → {name}")
            await toolset.close()
            return True
        else:
            fail(f"[{mcp_id}] Connected but 0 tools returned")
            await toolset.close()
            return False

    except asyncio.TimeoutError:
        fail(f"[{mcp_id}] Connection timed out (30s)")
        return False
    except Exception as exc:
        fail(f"[{mcp_id}] {exc}")
        return False


async def test_mcp_http(mcp: dict) -> bool:
    """Test an HTTP/SSE MCP server."""
    mcp_id = mcp["id"]
    url = mcp.get("url", "")

    if not url:
        # Dynamic URL from env
        env = _resolve_env(mcp)
        if env:
            for key in mcp.get("env_keys", []):
                if key.endswith("_URL") and env.get(key):
                    url = env[key]
                    break
    if not url:
        warn(f"[{mcp_id}] No URL configured and no env URL found.")
        return False

    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams

        params = StreamableHTTPConnectionParams(url=url)
        toolset = McpToolset(connection_params=params)
        tools = await asyncio.wait_for(toolset.get_tools(), timeout=15)

        if tools:
            ok(f"[{mcp_id}] HTTP connected — {len(tools)} tools")
            await toolset.close()
            return True
        else:
            fail(f"[{mcp_id}] HTTP connected but 0 tools")
            await toolset.close()
            return False

    except Exception as exc:
        fail(f"[{mcp_id}] HTTP connection failed: {exc}")
        return False


async def test_mcp_oauth(mcp: dict) -> bool:
    """OAuth MCPs need user tokens — just verify the URL is reachable."""
    import httpx

    url = mcp.get("url", "")
    if not url:
        warn(f"[{mcp['id']}] No URL configured.")
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            # OAuth MCP servers typically return 401 without token, which is expected
            if resp.status_code in (200, 401, 403, 405):
                ok(f"[{mcp['id']}] URL reachable (status {resp.status_code}) — needs OAuth flow")
                return True
            else:
                fail(f"[{mcp['id']}] Unexpected status {resp.status_code}")
                return False
    except Exception as exc:
        fail(f"[{mcp['id']}] Cannot reach URL: {exc}")
        return False


async def test_mcp(mcp: dict) -> bool:
    """Route to the right test based on MCP kind."""
    kind = mcp.get("kind", "")
    if kind == "mcp_stdio":
        return await test_mcp_stdio(mcp)
    elif kind == "mcp_http":
        return await test_mcp_http(mcp)
    elif kind == "mcp_oauth":
        return await test_mcp_oauth(mcp)
    elif kind == "e2b":
        ok(f"[{mcp['id']}] E2B — requires E2B_API_KEY at runtime")
        return True
    else:
        warn(f"[{mcp['id']}] Unknown kind: {kind}")
        return False


# ── Native Plugin Tests ─────────────────────────────────────────────


def test_native_plugin(plugin: dict) -> bool:
    """Test a native Python plugin by loading its factory."""
    plugin_id = plugin["id"]

    # Check env
    if plugin.get("requires_auth", False):
        missing = [k for k in plugin.get("env_keys", []) if not os.environ.get(k)]
        if missing:
            warn(f"[{plugin_id}] Missing env: {', '.join(missing)}")
            # Still try loading — factory may work without auth
            pass

    try:
        mod = importlib.import_module(plugin["module"])
        factory = getattr(mod, plugin["factory"])
        tools = factory()

        if tools:
            ok(f"[{plugin_id}] Loaded — {len(tools)} tools")
            for t in tools:
                info(f"  → {t.name}")
            return True
        else:
            fail(f"[{plugin_id}] Factory returned 0 tools")
            return False

    except Exception as exc:
        fail(f"[{plugin_id}] Import/factory failed: {exc}")
        return False


# ── Main ────────────────────────────────────────────────────────────


def list_all() -> None:
    """Print all discovered plugins."""
    mcps = discover_mcps()
    plugins = discover_native_plugins()

    header("MCP Servers (JSON configs)")
    for m in mcps:
        env_status = "🔑" if m.get("requires_auth") else "🆓"
        has_keys = all(os.environ.get(k) for k in m.get("env_keys", [])) if m.get("env_keys") else True
        key_color = GREEN if has_keys else RED
        print(f"  {env_status} {BOLD}{m['id']:<25}{RESET} {DIM}{m.get('kind', '?'):<12}{RESET} {key_color}{'keys ✔' if has_keys else 'keys missing'}{RESET}")
        if not has_keys:
            missing = [k for k in m.get("env_keys", []) if not os.environ.get(k)]
            print(f"     {DIM}→ set: {', '.join(missing)}{RESET}")

    header("Native Python Plugins")
    for p in plugins:
        print(f"  {BOLD}{p['id']:<25}{RESET} {DIM}{p['module']}{RESET}")


async def run_tests(target_mcp: str | None = None, target_native: str | None = None) -> None:
    mcps = discover_mcps()
    plugins = discover_native_plugins()
    results: dict[str, bool | None] = {}

    if target_mcp:
        # Test specific MCP
        mcp = next((m for m in mcps if m["id"] == target_mcp), None)
        if mcp is None:
            fail(f"MCP '{target_mcp}' not found. Use --list to see available.")
            sys.exit(1)
        header(f"Testing MCP: {mcp['name']}")
        results[mcp["id"]] = await test_mcp(mcp)

    elif target_native:
        # Test specific native plugin
        plugin = next((p for p in plugins if p["id"] == target_native or target_native in p["id"]), None)
        if plugin is None:
            fail(f"Native plugin '{target_native}' not found. Use --list to see available.")
            sys.exit(1)
        header(f"Testing Native Plugin: {plugin['name']}")
        results[plugin["id"]] = test_native_plugin(plugin)

    else:
        # Interactive: test all
        header("Testing All MCP Servers")
        for mcp in mcps:
            print(f"\n  {BOLD}→ {mcp['id']}{RESET} ({mcp.get('kind', '?')})")
            results[mcp["id"]] = await test_mcp(mcp)

        header("Testing All Native Plugins")
        for plugin in plugins:
            print(f"\n  {BOLD}→ {plugin['id']}{RESET}")
            results[plugin["id"]] = test_native_plugin(plugin)

    # ── Summary ─────────────────────────────────────────────────────
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)

    header("Summary")
    for name, status in results.items():
        if status is True:
            print(f"  {GREEN}✔{RESET} {name}")
        elif status is False:
            print(f"  {RED}✘{RESET} {name}")
        else:
            print(f"  {YELLOW}⚠{RESET} {name}")

    color = GREEN if failed == 0 else RED
    print(f"\n  {color}{passed} passed, {failed} failed, {skipped} skipped / {total} total{RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Omni MCP servers and plugins")
    parser.add_argument("--list", action="store_true", help="List all plugins and their key status")
    parser.add_argument("--mcp", type=str, help="Test a specific MCP by ID (e.g. github, brave-search)")
    parser.add_argument("--native", type=str, help="Test a specific native plugin by ID (e.g. google-jules)")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Omni MCP & Plugin Test Runner{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    if args.list:
        list_all()
        return

    asyncio.run(run_tests(target_mcp=args.mcp, target_native=args.native))


if __name__ == "__main__":
    main()
