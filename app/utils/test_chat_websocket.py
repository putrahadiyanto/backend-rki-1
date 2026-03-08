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


async def main():
    token = await get_token()
    print(f"🔑 Got JWT token: {token[:20]}...\n")

    async with websockets.connect(WS_URI) as ws:
        # 1. Authenticate
        await ws.send(json.dumps({"action": "authenticate", "token": token}))
        print(f"→ authenticate\n← {await ws.recv()}\n")

        # 2. Create session
        await ws.send(json.dumps({"action": "create_session"}))
        resp = json.loads(await ws.recv())
        print(f"→ create_session\n← {json.dumps(resp, indent=2)}\n")
        session_id = resp["session_id"]

        # 3. Send a message
        await ws.send(json.dumps({
            "action": "send_message",
            "session_id": session_id,
            "content": "Apa itu machine learning?",
        }))
        resp = json.loads(await ws.recv())
        print(f"→ send_message\n← {json.dumps(resp, indent=2)}\n")

        # 4. Send a follow-up (multi-turn)
        await ws.send(json.dumps({
            "action": "send_message",
            "session_id": session_id,
            "content": "Beri contoh penerapannya di bidang kesehatan.",
        }))
        resp = json.loads(await ws.recv())
        print(f"→ send_message (follow-up)\n← {json.dumps(resp, indent=2)}\n")

        # 5. Get history
        await ws.send(json.dumps({
            "action": "get_history",
            "session_id": session_id,
        }))
        resp = json.loads(await ws.recv())
        print(f"→ get_history\n← {len(resp.get('messages', []))} messages\n")

        # 6. List sessions
        await ws.send(json.dumps({"action": "list_sessions"}))
        resp = json.loads(await ws.recv())
        print(f"→ list_sessions\n← {json.dumps(resp, indent=2)}\n")

        # 7. Delete session
        await ws.send(json.dumps({
            "action": "delete_session",
            "session_id": session_id,
        }))
        print(f"→ delete_session\n← {await ws.recv()}\n")

    print("✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
