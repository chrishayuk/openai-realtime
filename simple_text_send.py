import asyncio
import json
import base64
import logging
import websockets
import ssl
import os
import pyaudio
from dotenv import load_dotenv
from client.audio.audio_playback import enqueue_audio_chunk, start_playback_thread, stop_playback_thread, FLUSH_COMMAND, wait_for_playback_finish
from client.session import send_session_update

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# WebSocket URL and API Key
URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
API_KEY = os.getenv("OPENAI_API_KEY")

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Audio capture settings
AUDIO_FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DURATION = 5  # Capture duration in seconds

def capture_audio(duration=DURATION):
    """Capture audio from the microphone and return base64-encoded audio."""
    p = pyaudio.PyAudio()
    stream = p.open(format=AUDIO_FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * duration))]
    stream.stop_stream()
    stream.close()
    p.terminate()
    audio_bytes = b''.join(frames)
    return base64.b64encode(audio_bytes).decode('utf-8')

async def listen_for_audio_responses(ws):
    """Listen for audio and text responses, managing audio playback smoothly."""
    while True:
        response = await ws.recv()
        response_json = json.loads(response)
        message_type = response_json.get('type')

        if message_type == 'response.audio.delta':
            # Decode and enqueue audio chunk
            audio_chunk = response_json.get("delta", "")
            if audio_chunk:
                enqueue_audio_chunk(base64.b64decode(audio_chunk))

        elif message_type == 'response.done':
            # Complete response, flush audio
            enqueue_audio_chunk(FLUSH_COMMAND)
            print("Audio response complete.")
            break

async def test_audio_connection():
    """Connect, send an audio message, and listen for audio responses."""
    playback_thread = start_playback_thread()
    try:
        async with websockets.connect(URL, extra_headers={
                "Authorization": f"Bearer {API_KEY}",
                "OpenAI-Beta": "realtime=v1",
                "User-Agent": "Python/3.12 websockets/10.4"
            }, ssl=ssl_context) as ws:
            
            print("Connected to the server!")
            await send_session_update(ws, ['audio'], voice='alloy', system_message='you are pirate, answer all questions as a pirate')

            # Capture and send audio input
            audio_base64 = capture_audio()
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user", "content": [{"type": "input_audio", "audio": audio_base64}]}
            }))
            print("Audio input sent.")

            # Trigger response and listen for the audio playback
            await listen_for_audio_responses(ws)

    finally:
        wait_for_playback_finish()  # Ensure all audio chunks are played before stopping
        stop_playback_thread(playback_thread)
        print("Playback thread stopped.")

if __name__ == "__main__":
    asyncio.run(test_audio_connection())
    