"""
Test script for the /ws/chat WebSocket endpoint.
Requires a running server and valid credentials.

Usage:
    python -m app.utils.test_chat_websocket
"""

import asyncio
import json
import httpx
import websockets


SERVER = "http://localhost:8000"
WS_URI = "ws://localhost:8000/ws/chat"

# Use an existing user or register one first via POST /auth/register
USERNAME = "admin"
PASSWORD = "admin"


async def get_token() -> str:
    """Log in via REST and return a JWT token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SERVER}/auth/token",
            data={"username": USERNAME, "password": PASSWORD},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def print_separator(label: str):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")


async def main():
    token = await get_token()
    print(f"🔑 Got JWT token: {token[:20]}...\n")

    async with websockets.connect(WS_URI) as ws:
        # ── 1. Authenticate ──────────────────────────────────────
        print_separator("1. Authenticate")
        await ws.send(json.dumps({"action": "authenticate", "token": token}))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2)}")

        # ── 2. Create session ────────────────────────────────────
        print_separator("2. Create Session")
        await ws.send(json.dumps({"action": "create_session"}))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2)}")
        session_id = resp["session_id"]

        # ── 3. Send message: apa itu jantung ─────────────────────
        print_separator("3. Send Message — Apa itu jantung?")
        await ws.send(json.dumps({
            "action": "send_message",
            "session_id": session_id,
            "content": "Apa itu jantung dan apa fungsinya?",
        }))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2, ensure_ascii=False)}")

        # ── 4. Follow-up: paru-paru ──────────────────────────────
        print_separator("4. Send Message — Lalu bagaimana dengan paru-paru?")
        await ws.send(json.dumps({
            "action": "send_message",
            "session_id": session_id,
            "content": "Lalu bagaimana dengan paru-paru? Apa fungsinya?",
        }))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2, ensure_ascii=False)}")

        # ── 5. Follow-up: ginjal ─────────────────────────────────
        print_separator("5. Send Message — Kalau ginjal?")
        await ws.send(json.dumps({
            "action": "send_message",
            "session_id": session_id,
            "content": "Kalau ginjal, fungsinya apa?",
        }))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2, ensure_ascii=False)}")

        # ── 6. Get full chat history (should have 6 messages) ────
        print_separator("6. Get Chat History (should have 6 messages: 3 user + 3 assistant)")
        await ws.send(json.dumps({
            "action": "get_history",
            "session_id": session_id,
        }))
        resp = json.loads(await ws.recv())
        messages = resp.get("messages", [])
        print(f"Total messages: {len(messages)}\n")
        for i, msg in enumerate(messages, 1):
            role_icon = "👤 User" if msg["role"] == "user" else "🤖 Assistant"
            print(f"  [{i}] {role_icon}:")
            # Truncate long assistant responses for readability
            content = msg["content"]
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"      {content}\n")

        # ── 7. List sessions ─────────────────────────────────────
        print_separator("7. List Sessions")
        await ws.send(json.dumps({"action": "list_sessions"}))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2, ensure_ascii=False)}")

        # ── 8. Delete session ────────────────────────────────────
        print_separator("8. Delete Session")
        await ws.send(json.dumps({
            "action": "delete_session",
            "session_id": session_id,
        }))
        resp = json.loads(await ws.recv())
        print(f"← {json.dumps(resp, indent=2)}")

    print(f"\n{'='*60}")
    print("  ✅ All tests passed!")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
