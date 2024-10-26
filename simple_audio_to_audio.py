import asyncio
import json
import base64
import pyaudio
import websockets
import ssl
import os
import sys
from dotenv import load_dotenv
from client.audio.audio_message_sender import trigger_response
from client.session import send_session_update

# Load environment variables
load_dotenv()

# WebSocket URL and API Key
URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("Error: OPENAI_API_KEY environment variable not set.")

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DURATION = 5  # seconds

def capture_audio(duration=DURATION):
    """Capture audio from the microphone and return base64-encoded audio."""
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * duration))]
    stream.stop_stream()
    stream.close()
    p.terminate()
    audio_bytes = b''.join(frames)
    return base64.b64encode(audio_bytes).decode('utf-8')

def play_audio(audio_bytes):
    """Play the audio bytes using PyAudio."""
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)
    stream.write(audio_bytes)
    stream.stop_stream()
    stream.close()
    p.terminate()

async def listen_for_responses(ws):
    """Listen for and process audio and text responses from the WebSocket server."""
    while True:
        response = json.loads(await ws.recv())
        message_type = response.get('type')

        if message_type == 'response.audio.delta':
            audio_chunk = response.get("delta", "")
            #print(audio_chunk)
            if audio_chunk:
                play_audio(base64.b64decode(audio_chunk))

        elif message_type == 'response.done':
            status = response.get('response', {}).get('status')
            if status == 'completed':
                transcript = response.get('response', {}).get('output', [{}])[0].get('content', [{}])[0].get('transcript', '')
                print(f"\nAssistant transcript: {transcript}")
            elif status == 'failed':
                error_message = response.get('response', {}).get('status_details', {}).get('error', {}).get('message', 'Unknown error.')
                print(f"Server error: {error_message}")
            break

async def test_audio_to_audio():
    """Connect to the WebSocket, send an audio message, and handle responses."""
    async with websockets.connect(URL, extra_headers={
            "Authorization": f"Bearer {API_KEY}",
            "OpenAI-Beta": "realtime=v1",
            "User-Agent": "Python/3.12 websockets/10.4"
        }, ssl=ssl_context) as ws:
        
        print("Connected to server.")
        
        # Send session update
        await send_session_update(ws, ['text', 'audio'], voice='alloy', system_message='you are pirate, answer all questions as a pirate')
        print("Session update sent.")
        
        # Capture and send audio
        audio_base64 = capture_audio()
        await ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_audio", "audio": audio_base64}]
            }
        }))
        print("Sent audio input.")
        
        # Trigger response and listen for responses
        await trigger_response(ws, ['text', 'audio'], 'you are pirate, answer all questions as a pirate', 'alloy')
        await listen_for_responses(ws)

# Run the test
if __name__ == "__main__":
    asyncio.run(test_audio_to_audio())
