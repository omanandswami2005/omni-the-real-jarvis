"""Test Courier API key validity by calling the /send endpoint."""

import asyncio
import os
import sys

import httpx

API_KEY = os.environ.get("COURIER_API_KEY", "")
COURIER_SEND_URL = "https://api.courier.com/send"
COURIER_BRANDS_URL = "https://api.courier.com/brands"  # lightweight GET for auth check


async def test_auth():
    """Test 1: Verify API key is accepted by Courier."""
    print("\n── Test 1: Auth Check (GET /brands) ──")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            COURIER_BRANDS_URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Brands found: {len(data.get('results', []))}")
            print("  ✅ AUTH OK")
            return True
        else:
            print(f"  Response: {resp.text[:200]}")
            print("  ❌ AUTH FAILED")
            return False


async def test_send_dry():
    """Test 2: Send a test notification (to a valid courier test email)."""
    print("\n── Test 2: Send Test Notification ──")
    payload = {
        "message": {
            "to": {"email": "test@courier.com"},
            "content": {
                "title": "Omni Test",
                "body": "This is a test notification from Omni Hub.",
            },
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            COURIER_SEND_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code in (200, 202):
            data = resp.json()
            print(f"  Request ID: {data.get('requestId', 'N/A')}")
            print("  ✅ SEND OK")
            return True
        elif resp.status_code == 401:
            print("  ❌ Unauthorized — invalid API key")
            return False
        else:
            print(f"  Response: {resp.text[:300]}")
            # 400/422 with a valid auth still means the key works
            if resp.status_code in (400, 422):
                print("  ⚠️  Key is valid but request body may need adjustment")
                return True
            print("  ❌ SEND FAILED")
            return False


async def test_whoami():
    """Test 3: Check API key details via /auth/whoami."""
    print("\n── Test 3: Whoami Check ──")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.courier.com/auth/whoami",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Tenant: {data.get('tenant_name', 'N/A')}")
            print(f"  Scope: {data.get('scope', 'N/A')}")
            print("  ✅ WHOAMI OK")
            return True
        else:
            print(f"  Response: {resp.text[:200]}")
            print("  ❌ WHOAMI FAILED")
            return False


async def main():
    if not API_KEY:
        print("❌ COURIER_API_KEY not set")
        sys.exit(1)

    print(f"Testing Courier API key: {API_KEY[:10]}...{API_KEY[-4:]}")

    results = []
    results.append(await test_auth())
    results.append(await test_send_dry())
    results.append(await test_whoami())

    passed = sum(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{len(results)} tests passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
