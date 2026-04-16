"""
This script provides a command-line interface to manually test the chat WebSocket functionality.

It allows you to:
1.  Connect to the WebSocket.
2.  Authenticate using a JWT token.
3.  Create a new chat session.
4.  Send messages and receive responses from the LLM.
5.  See the full JSON response, including thoughts, actions, and game data.

**Prerequisites:**
*   The backend server must be running.
*   You must have a valid JWT token obtained from the `/auth/token` endpoint.

**Usage:**
1.  Run the script: `python -m app.utils.test_chat_websocket`
2.  Paste your JWT token when prompted.
3.  Follow the on-screen instructions to send messages.
"""
import asyncio
import websockets
import json
import os
import httpx

# --- Configuration -----------------------------------------------------------
# Get the backend URL from environment variables, with a default
SERVER_URL = os.getenv("SERVER_URL", "http://43.157.235.115:8000")
WS_URL = os.getenv("WS_URL", "ws://43.157.235.115:8000")
TOKEN_FILE = ".chattest_token"

# --- Credentials for fetching a new token ------------------------------------
# You can change these or set them as environment variables
USERNAME = os.getenv("TEST_USERNAME", "admin")
PASSWORD = os.getenv("TEST_PASSWORD", "admin")


# --- Token Management Functions ----------------------------------------------

async def get_new_token() -> str | None:
    """Fetch a new JWT token from the /auth/token endpoint."""
    print(f"\nAttempting to fetch a new token for user '{USERNAME}'...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVER_URL}/auth/token",
                data={"username": USERNAME, "password": PASSWORD}
            )
            response.raise_for_status()  # Raises an exception for 4XX/5XX responses
            token = response.json().get("access_token")
            if token:
                print("--- Successfully fetched new token. ---")
                save_token(token)
                return token
            else:
                print("--- Error: 'access_token' not found in response. ---")
                return None
    except httpx.HTTPStatusError as e:
        print(f"--- HTTP error fetching token: {e.response.status_code} {e.response.text} ---")
        return None
    except httpx.RequestError as e:
        print(f"--- Network error fetching token: {e} ---")
        return None

def save_token(token: str):
    """Save the token to a local file."""
    try:
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print(f"--- Token saved to {TOKEN_FILE} ---")
    except IOError as e:
        print(f"--- Error saving token to file: {e} ---")

def load_token() -> str | None:
    """Load the token from a local file."""
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            print(f"--- Token loaded from {TOKEN_FILE} ---")
            return token
    except IOError as e:
        print(f"--- Error loading token from file: {e} ---")
        return None

# -----------------------------------------------------------------------------

async def main():
    """Main function to run the WebSocket test client."""
    print("--- RKI Chat WebSocket Tester ---")
    print(f"Connecting to: {WS_URL}")

    token = load_token()
    if not token:
        token = await get_new_token()

    if not token:
        print("\nCould not obtain a token. Please check your credentials and server status.")
        print("You can set TEST_USERNAME and TEST_PASSWORD environment variables.")
        return

    try:
        async with websockets.connect(f"{WS_URL}/ws/chat") as websocket:
            print("\n[Step 1] WebSocket Connection Successful")

            # Authenticate the WebSocket connection
            await websocket.send(json.dumps({
                "action": "authenticate",
                "token": token
            }))
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)

            # If token is invalid/expired, get a new one and retry
            if "error" in auth_data:
                print(f"--- Authentication failed: {auth_data.get('error')} ---")
                print("--- The saved token might be expired. Fetching a new one. ---")
                token = await get_new_token()
                if not token:
                    print("Could not get a new token. Exiting.")
                    return

                # Retry authentication with the new token
                await websocket.send(json.dumps({
                    "action": "authenticate",
                    "token": token
                }))
                auth_response = await websocket.recv()
                auth_data = json.loads(auth_response)
                if "error" in auth_data:
                    print(f"--- Authentication still failed with new token: {auth_data.get('error')}. Exiting. ---")
                    return

            print(f"<<< AUTH: {json.dumps(auth_data)}")
            print("--- Authentication successful! ---")


            # Create a new chat session
            # Create a new chat session via HTTP POST /sessions
            print("\n[Step 2] Creating a new chat session via HTTP API...")
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.post(
                        f"{SERVER_URL}/chat/sessions",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10.0,
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    session_id = body.get("session_id")
                    if not session_id:
                        print(f"Failed to create session: unexpected response {body}")
                        return
                    print(f"--- Session created: {session_id} ---")
                except Exception as e:
                    print(f"Failed to create session via HTTP: {e}")
                    return


            # Chat loop
            print("\n[Step 3] Start chatting!")
            print("Type your message and press Enter. Type 'quit' to exit.")
            while True:
                message = input("\n> ")
                if message.lower() == 'quit':
                    print("--- Exiting chat. ---")
                    break

                await websocket.send(json.dumps({
                    "action": "send_message",
                    "session_id": session_id,
                    "content": message
                }))

                # Receive and print the full response from the backend
                response = await websocket.recv()
                try:
                    data = json.loads(response)
                    action = data.get("action", "chat_response")
                    assistant = data.get("assistant_message", {})
                    thoughts = data.get("thoughts", "")

                    print()
                    if thoughts:
                        print(f"[思考] {thoughts}\n")

                    print(f"[{action}] {assistant.get('content', '')}")

                    if action == "trigger_minigame":
                        game = data.get("game_data", {})
                        print(f"\n  Topic   : {game.get('topic', '')}")
                        for i, q in enumerate(game.get("questions", []), 1):
                            print(f"\n  Q{i}: {q['question_text']}")
                            for j, opt in enumerate(q.get("answer_options", [])):
                                marker = "✓" if j == q.get("correct_answer_index") else " "
                                print(f"    [{marker}] {opt}")

                    if "error" in data:
                        print(f"[ERROR] {data['error']}")
                except json.JSONDecodeError:
                    print(f"Received non-JSON response: {response}")

    except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError) as e:
        print(f"\nConnection failed: {e}")
        print(f"Please ensure the backend server is running and accessible at {WS_URL}.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    # Ensure the script is run from the project root
    # so that the `app` module can be found.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n--- Script interrupted by user. ---")