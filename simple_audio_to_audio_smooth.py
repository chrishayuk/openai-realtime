import asyncio
import json
import base64
import logging
import websockets
import ssl
import os
import sys
import pyaudio
from dotenv import load_dotenv
from client.session import send_session_update
from client.audio.audio_message_sender import trigger_response
from client.audio.audio_playback import start_playback_thread, stop_playback_thread, enqueue_audio_chunk, FLUSH_COMMAND, wait_for_playback_finish

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# WebSocket URL and API Key
URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
API_KEY = os.getenv("OPENAI_API_KEY")

# Ensure API Key is set
if not API_KEY:
    print("Error: OPENAI_API_KEY environment variable not set.")
    sys.exit(1)

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DURATION = 5  # seconds

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def capture_audio(duration=DURATION):
    """Capture audio from the microphone and return base64-encoded audio."""
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    logger.debug("Recording audio...")
    frames = []

    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    logger.debug("Audio recording complete.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    audio_bytes = b''.join(frames)
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    return audio_base64

async def test_audio_to_audio():
    """Connect to the server, send an audio message, and listen for audio responses with smooth playback."""
    # Start the playback thread
    playback_thread = start_playback_thread()
    logger.debug("Playback thread started.")

    async with websockets.connect(URL, extra_headers={
            "Authorization": f"Bearer {API_KEY}",
            "OpenAI-Beta": "realtime=v1",
            "User-Agent": "Python/3.12 websockets/10.4"
        }, ssl=ssl_context) as websocket:
        
        logger.debug("Connected to server.")

        # Send session update
        await send_session_update(websocket, ['text', 'audio'], voice='alloy', system_message='you are pirate, answer all questions as a pirate')
        logger.debug("Session update sent.")

        # Receive initial session.created
        initial_response = await websocket.recv()
        logger.debug(f"Received initial response: {initial_response}")

        # Capture and send audio input
        audio_base64 = capture_audio()
        conversation_item_create = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "audio": audio_base64
                    }
                ]
            }
        }

        # Send the audio message
        await websocket.send(json.dumps(conversation_item_create))
        logger.debug("Sent audio input.")

        # Trigger response
        await trigger_response(websocket, ['text', 'audio'], 'you are pirate, answer all questions as a pirate', 'alloy')

        # Listen for audio and text responses
        try:
            while True:
                response = await websocket.recv()
                logger.debug(f"Received response: {response}")

                response_json = json.loads(response)
                message_type = response_json.get('type')

                if message_type == 'response.audio.delta':
                    # Decode and enqueue audio for playback
                    audio_base64 = response_json.get("delta", "")
                    if audio_base64:
                        audio_bytes = base64.b64decode(audio_base64)
                        enqueue_audio_chunk(audio_bytes)  # Enqueue audio chunk for smooth playback

                elif message_type == 'response.done':
                    # Complete response, flush the audio queue
                    enqueue_audio_chunk(FLUSH_COMMAND)  # Signal end of audio playback
                    status = response_json.get('response', {}).get('status')
                    if status == 'completed':
                        transcript = response_json.get('response', {}).get('output', [{}])[0].get('content', [{}])[0].get('transcript', '')
                        print(f"\nAssistant transcript: {transcript}")
                    elif status == 'failed':
                        error_message = response_json.get('response', {}).get('status_details', {}).get('error', {}).get('message', 'Unknown error.')
                        logger.error(f"Server error: {error_message}")
                    break  # Exit loop after handling 'response.done'

        except websockets.exceptions.ConnectionClosed:
            logger.debug("Connection closed.")

    # Wait for all audio to finish before stopping the playback thread
    wait_for_playback_finish()
    stop_playback_thread(playback_thread)
    logger.debug("Playback thread stopped.")

if __name__ == "__main__":
    asyncio.run(test_audio_to_audio())
