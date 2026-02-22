import asyncio
import websockets
import json

async def test_voice_assistant():
    # Replace with your VPS IP or 'localhost' if testing locally
    uri = "ws://localhost:8000/ws/voice"
    audio_file_path = "data/audio/test.mp3"  # Make sure this file exists

    async with websockets.connect(uri) as websocket:
        print(f"📡 Connected to {uri}")

        with open(audio_file_path, "rb") as f:
            print("🎤 Streaming audio chunks...")
            while True:
                chunk = f.read(4096)  # Send in 4KB chunks
                if not chunk:
                    break
                await websocket.send(chunk)
                await asyncio.sleep(0.01)  # Mimic real-time microphone stream

        # Signal the backend that we are done talking
        print("💡 Sending END_OF_SPEECH signal...")
        await websocket.send("END_OF_SPEECH")

        # Wait for the JSON response
        response = await websocket.recv()
        data = json.loads(response)

        print(f"raw response: {data}")

        print("\n--- Backend Response ---")
        print(f"📝 STT Result: {data.get('stt')}")
        print(f"🧠 Thinking: {data.get('thinking')}")
        print(f"🔊 Answer (for TTS): {data.get('answer')}")

if __name__ == "__main__":
    asyncio.run(test_voice_assistant())