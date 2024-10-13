import asyncio
import base64
import io
import json
import sounddevice as sd
import numpy as np
from pydub import AudioSegment

# Function to create a conversation.item.create event for audio input
def audio_to_item_create_event(audio_bytes: bytes) -> str:
    """Convert audio bytes to conversation.item.create event."""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    
    # Resample to 24kHz mono pcm16
    pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2).raw_data
    
    # Encode to base64 string
    pcm_base64 = base64.b64encode(pcm_audio).decode()
    
    event = {
        "type": "conversation.item.create", 
        "item": {
            "type": "message",
            "role": "user",
            "content": [{
                "type": "input_audio", 
                "audio": pcm_base64
            }]
        }
    }
    return json.dumps(event)

# Function to check if the audio chunk is mostly silent
def is_silent(indata, threshold=100):
    """Check if the audio data is mostly silence based on a threshold."""
    return np.abs(indata).mean() < threshold

# Function to send audio from a file as a conversation item
async def send_audio_file(ws, file_path):
    """Send audio from a file."""
    try:
        with open(file_path, 'rb') as f:
            audio_bytes = f.read()
        event = audio_to_item_create_event(audio_bytes)
        await ws.send(event)
    except Exception as e:
        print(f"Error while sending audio file: {e}")

# Function to send microphone audio
async def send_microphone_audio(ws):
    """Capture microphone audio with sounddevice, convert it to 16-bit PCM, and send it via WebSocket."""
    try:
        # Audio configuration
        RATE = 24000  # 24kHz sampling rate
        CHANNELS = 1  # Mono audio
        CHUNK_DURATION = 0.5  # Duration of each audio chunk in seconds (500ms)

        # Calculate the chunk size based on the duration
        CHUNK = int(RATE * CHUNK_DURATION)
        audio_data_accumulated = b""

        print("Recording from microphone. Press Ctrl+C to stop.")

        # Get the event loop on the main thread
        loop = asyncio.get_event_loop()

        # Async callback function to handle audio data
        async def audio_callback(indata, frames, time, status):
            nonlocal audio_data_accumulated
            
            # Ensure indata is 16-bit PCM, flatten and convert to bytes
            pcm_audio = (indata * 32767).astype(np.int16).tobytes()

            # Only accumulate if the audio is not silent
            if not is_silent(indata):
                audio_data_accumulated += pcm_audio

            # Send accumulated data if it's large enough (> 1KB)
            if len(audio_data_accumulated) > 1024:
                # Convert to base64 for transmission
                audio_base64 = base64.b64encode(audio_data_accumulated).decode()

                # Create WebSocket event for PCM audio
                event = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{
                            "type": "input_audio",
                            "audio": audio_base64,
                            "format": "pcm16"  # Mark the format as 16-bit PCM
                        }]
                    }
                }

                # Send the event asynchronously
                await ws.send(json.dumps(event))
                print(f"Sending accumulated audio chunk over WebSocket: {len(audio_data_accumulated)} bytes")
                audio_data_accumulated = b""  # Clear the buffer after sending

        # Wrapper to call the async audio_callback from sounddevice callback
        def audio_callback_wrapper(indata, frames, time, status):
            # Schedule the async audio_callback within the main event loop
            loop.call_soon_threadsafe(asyncio.create_task, audio_callback(indata, frames, time, status))

        # Open stream using sounddevice
        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='int16', callback=audio_callback_wrapper):
            # Keep the stream open
            while True:
                await asyncio.sleep(0.1)  # Sleep to prevent blocking

    except Exception as e:
        print(f"Error while sending microphone audio: {e}")
