import asyncio
import json
import base64
import pyaudio
import websockets
import logging
import ssl
import os
import sys
from dotenv import load_dotenv
from audio_message_sender import trigger_response
from session import send_session_update

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DURATION = 5  # seconds

# WebSocket URL
URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

# Retrieve OpenAI API Key from environment
API_KEY = os.getenv("OPENAI_API_KEY")

# get the api key
if not API_KEY:
    print("Error: OPENAI_API_KEY environment variable not set.")
    sys.exit(1)

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def capture_audio(duration=DURATION):
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


def play_audio(audio_bytes):
    """Play the audio bytes using pyaudio."""
    p = pyaudio.PyAudio()

    # Open stream
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True)

    # Write audio data to the stream
    stream.write(audio_bytes)

    # Stop stream
    stream.stop_stream()
    stream.close()

    # Terminate pyaudio
    p.terminate()


async def test_audio_to_audio():
    uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "OpenAI-Beta": "realtime=v1",
        "User-Agent": "Python/3.12 websockets/10.4"
    }

    async with websockets.connect(uri, extra_headers=headers, ssl=ssl_context) as websocket:
        logger.debug("Connected to server.")

        # Send session update
        await send_session_update(websocket, ['text', 'audio'], voice='alloy', system_message='you are pirate, answer all questions as a pirate')

        # Receive session.created
        message = await websocket.recv()
        logger.debug(f"Received message: {message}")

        # Capture and send audio
        audio_base64 = capture_audio()
        conversation_item_create = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "audio": audio_base64      # Send audio data correctly encoded
                    }
                ]
            }
        }

        # Send the audio message to the WebSocket
        await websocket.send(json.dumps(conversation_item_create))
        logger.debug(f"Sent conversation.item.create: {conversation_item_create}")

        await trigger_response(websocket, ['text', 'audio'], 'you are pirate, answer all questions as a pirate', 'alloy')

        # Listen for responses
        try:
            while True:
                response = await websocket.recv()
                logger.debug(f"Received response: {response}")

                response_json = json.loads(response)
                message_type = response_json.get('type')

                if message_type == 'response.audio.delta':
                    # Decode the base64 audio
                    audio_base64 = response_json.get("delta", "")
                    if audio_base64:
                        audio_bytes = base64.b64decode(audio_base64)
                        # Play the audio chunk
                        play_audio(audio_bytes)

                elif message_type == 'response.done':
                    status = response_json.get('response', {}).get('status')
                    if status == 'completed':
                        transcript = response_json.get('response', {}).get('output', [{}])[0].get('content', [{}])[0].get('transcript', '')
                        print(f"Assistant: {transcript}")
                        break
                    elif status == 'failed':
                        error_message = response_json.get('response', {}).get('status_details', {}).get('error', {}).get('message', 'Unknown error.')
                        logger.error(f"Server error: {error_message}")
                        break

        except websockets.exceptions.ConnectionClosed:
            logger.debug("Connection closed.")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_audio_to_audio())
