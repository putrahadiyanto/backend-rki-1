import asyncio
import websockets
import json
import os
import httpx
import wave
import sys
import threading
from queue import Queue

BASE_URL = "ws://localhost:8000"
AUTH_URL = "http://localhost:8000"

# Try to import sounddevice for live microphone recording
try:
    import sounddevice as sd
    import numpy as np
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False


async def get_token():
    """Get a JWT token for authentication"""
    async with httpx.AsyncClient() as client:
        # Try to register first
        try:
            response = await client.post(
                f"{AUTH_URL}/auth/register",
                json={"username": "testuser", "password": "testpass123", "email": "test@example.com"}
            )
            print(f"Register attempt: {response.status_code}")
        except:
            pass
        
        # Try login with OAuth2 form
        try:
            response = await client.post(
                f"{AUTH_URL}/auth/token",
                data={"username": "testuser", "password": "testpass123"}
            )
            if response.status_code == 200:
                return response.json().get("access_token")
        except Exception as e:
            print(f"Error getting token: {e}")
            return None


async def create_test_audio(filename="test_audio.wav", duration=2):
    """Create a simple test audio file (silence)"""
    import wave
    import array
    
    sample_rate = 16000
    num_samples = sample_rate * duration
    
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        # Write silence
        silence = array.array('h', [0] * num_samples)
        wav_file.writeframes(silence.tobytes())
    
    print(f"Created test audio: {filename}")


def record_microphone(duration=5, sample_rate=16000):
    """Record audio from microphone and return as bytes"""
    if not HAS_SOUNDDEVICE:
        print("Error: sounddevice not installed. Install with: pip install sounddevice numpy")
        return None
    
    print(f"\n🎤 Recording for {duration} seconds...")
    print("   Speak now...")
    
    try:
        # Record audio
        audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()  # Wait for recording to finish
        
        print("✓ Recording complete!")
        
        # Convert to bytes
        audio_bytes = audio_data.tobytes()
        
        # Save to file for reference
        with wave.open("live_recording.wav", 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
        
        print(f"✓ Saved recording to: live_recording.wav")
        return audio_bytes
    
    except Exception as e:
        print(f"Error recording audio: {e}")
        return None


async def record_microphone_interactive(chunk_queue):
    """Record from microphone in real-time and put chunks in queue"""
    if not HAS_SOUNDDEVICE:
        print("Error: sounddevice not installed. Install with: pip install sounddevice numpy")
        return
    
    sample_rate = 16000
    chunk_duration = 0.5  # Send 500ms chunks
    chunk_samples = int(chunk_duration * sample_rate)
    
    print(f"\n🎤 Starting live microphone recording...")
    print("   Speaking in real-time mode. Press Ctrl+C to stop.")
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        # Convert audio data to bytes and put in queue
        chunk_queue.put(bytes(indata.astype('int16').tobytes()))
    
    try:
        with sd.InputStream(callback=audio_callback, channels=1, samplerate=sample_rate, 
                           blocksize=chunk_samples, dtype='int16'):
            print("✓ Microphone stream started")
            # Keep the stream running
            sd.sleep(int(60 * 1000))  # Run for 60 seconds max
    except KeyboardInterrupt:
        print("\n✓ Recording stopped")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        chunk_queue.put(None)  # Signal end of stream


async def test_voice_websocket():
    """Test voice websocket with full flow"""
    
    # Check for command-line arguments
    use_live_mic = "--live" in sys.argv or "--mic" in sys.argv
    audio_file = None
    
    # Check for --file or --audio parameter
    for i, arg in enumerate(sys.argv):
        if arg in ("--file", "--audio") and i + 1 < len(sys.argv):
            audio_file = sys.argv[i + 1]
            break
    
    if use_live_mic and not HAS_SOUNDDEVICE:
        print("Error: Live microphone mode requires sounddevice library")
        print("Install with: pip install sounddevice numpy")
        return
    
    # Step 1: Get authentication token
    print("\n=== Step 1: Getting authentication token ===")
    token = await get_token()
    if not token:
        print("Failed to get token. Make sure server is running and credentials are correct.")
        return
    print(f"✓ Got token: {token[:20]}...")
    
    # Step 2: Prepare audio
    print("\n=== Step 2: Preparing audio ===")
    if use_live_mic:
        print("Mode: LIVE MICROPHONE")
        audio_data = None  # Will be collected during streaming
        mode_label = "live microphone"
    elif audio_file:
        print(f"Mode: AUDIO FILE - {audio_file}")
        # Handle relative paths
        if not os.path.isabs(audio_file):
            audio_file = os.path.join(os.getcwd(), audio_file)
        
        if not os.path.exists(audio_file):
            print(f"Error: Audio file not found: {audio_file}")
            return
        
        try:
            with open(audio_file, "rb") as f:
                audio_data = f.read()
            print(f"✓ Loaded audio file: {len(audio_data)} bytes")
            mode_label = f"audio file ({os.path.basename(audio_file)})"
        except Exception as e:
            print(f"Error reading audio file: {e}")
            return
    else:
        print("Mode: TEST AUDIO (silence)")
        await create_test_audio()
        with open("test_audio.wav", "rb") as f:
            audio_data = f.read()
        mode_label = "test audio"
    
    # Step 3: Connect to WebSocket
    print("\n=== Step 3: Connecting to voice WebSocket ===")
    uri = f"{BASE_URL}/ws/voice"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected to {uri}")
            
            # Step 4: Authenticate
            print("\n=== Step 4: Authenticating ===")
            auth_msg = {
                "action": "authenticate",
                "token": token
            }
            await websocket.send(json.dumps(auth_msg))
            response = await websocket.recv()
            print(f"✓ Auth response: {response}")
            
            # Step 5: Create session
            print("\n=== Step 5: Creating session ===")
            session_msg = {"action": "create_session"}
            await websocket.send(json.dumps(session_msg))
            response = await websocket.recv()
            response_data = json.loads(response)
            session_id = response_data.get("session_id")
            print(f"✓ Session created: {session_id}")
            
            # Step 6: Send audio chunks
            print(f"\n=== Step 6: Sending {mode_label} ===")
            
            if use_live_mic:
                # Live microphone mode
                chunk_queue = Queue()
                
                # Start recording in background thread
                record_thread = threading.Thread(
                    target=lambda: asyncio.run(record_microphone_interactive(chunk_queue)),
                    daemon=True
                )
                record_thread.start()
                
                # Send chunks as they arrive
                chunk_count = 0
                while True:
                    try:
                        chunk = chunk_queue.get(timeout=1.0)
                        if chunk is None:
                            print("✓ Live recording finished")
                            break
                        await websocket.send(chunk)
                        chunk_count += 1
                        if chunk_count % 10 == 0:
                            print(f"  Sent {chunk_count} audio chunks...")
                    except:
                        pass
            else:
                # Test audio mode
                chunk_size = 4096
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i + chunk_size]
                    await websocket.send(chunk)
                    print(f"  Sent audio chunk {i // chunk_size + 1}")
            
            # Step 7: Signal end of speech
            print("\n=== Step 7: Processing audio (end_of_speech) ===")
            end_msg = {
                "action": "end_of_speech",
                "session_id": session_id
            }
            await websocket.send(json.dumps(end_msg))
            
            # Wait for response (may take a moment)
            print("Waiting for response...")
            response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
            response_data = json.loads(response)
            print(f"✓ Response: {json.dumps(response_data, indent=2)}")
            
            # Step 8: Test session management
            print("\n=== Step 8: Testing session management ===")
            
            # List sessions
            list_msg = {"action": "list_sessions"}
            await websocket.send(json.dumps(list_msg))
            response = await websocket.recv()
            print(f"✓ Sessions retrieved")
            
            # Get history
            history_msg = {
                "action": "get_history",
                "session_id": session_id
            }
            await websocket.send(json.dumps(history_msg))
            response = await websocket.recv()
            print(f"✓ History retrieved")
            
            print("\n✓ Test completed successfully!")
    
    except asyncio.TimeoutError:
        print("Timeout waiting for response. Check server logs.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Voice WebSocket Test")
    print("=" * 50)
    print("Make sure your FastAPI server is running on localhost:8000\n")
    
    if "--live" in sys.argv or "--mic" in sys.argv:
        print("Mode: LIVE MICROPHONE")
        if not HAS_SOUNDDEVICE:
            print("\n❌ sounddevice not installed!")
            print("Install with: pip install sounddevice numpy")
            sys.exit(1)
        print("\nSetup: Make sure your microphone is connected and working")
    else:
        print("Usage:")
        print("  Default (test audio):")
        print("    python app/utils/test_voice_webscoket.py")
        print("\n  Live microphone:")
        print("    python app/utils/test_voice_webscoket.py --live")
        print("\n  Audio file:")
        print("    python app/utils/test_voice_webscoket.py --file ../../data/audio/jantung.mp3")
        print("    or")
        print("    python app/utils/test_voice_webscoket.py --audio path/to/audio.mp3")
    
    print("\n" + "=" * 50)
    asyncio.run(test_voice_websocket())