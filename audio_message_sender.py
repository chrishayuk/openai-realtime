import numpy as np
import io
import json
import base64
import sounddevice as sd
import asyncio
import logging
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# Function to create a conversation.item.create event for audio input
def audio_to_item_create_event(audio_bytes: bytes) -> str:
    """Convert audio bytes to conversation.item.create event."""
    # Load the audio file from the byte stream and resample it to 24kHz mono PCM16
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    
    # Resample to 24kHz mono pcm16
    pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2).raw_data
    
    # Encode to base64 string
    pcm_base64 = base64.b64encode(pcm_audio).decode()
    
    # Construct the WebSocket event
    event = {
        "type": "conversation.item.create", 
        "item": {
            "type": "message",
            "role": "user",
            "content": [{
                "type": "input_audio", 
                "audio": pcm_base64,  # Use the resampled and encoded PCM audio
            }]
        }
    }
    return json.dumps(event)

# Function to check if the audio chunk is mostly silent
def is_silent(pcm_audio, threshold=100):
    """Check if the audio data is mostly silence based on RMS."""
    try:
        # Get audio data from buffer
        audio_data = np.frombuffer(pcm_audio, dtype=np.int16)

        # Ensure we have data
        if len(audio_data) == 0:
            return True
        
        # Check if all samples are zero
        if np.all(audio_data == 0):
            return True
        
        # Check for invalid or out-of-range values
        if np.any(np.isnan(audio_data)) or np.max(np.abs(audio_data)) > 32767:
            return True
        
        # Suppress warnings for invalid values (such as sqrt of NaN or negative numbers)
        with np.errstate(invalid='ignore'):
            # Calculate the RMS, allowing for NaN or invalid values
            rms = np.sqrt(np.mean(np.square(audio_data)))

        # Return True if RMS is below threshold, meaning it's silent
        return rms < threshold
    except (ValueError, OverflowError) as e:
        logger.error(f"Error processing audio data for RMS: {e}")
        return True



# Function to create a conversation.item.create event for audio input
def audio_to_item_create_event(audio_bytes: bytes) -> str:
    """Convert audio bytes to conversation.item.create event."""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2).raw_data
    pcm_base64 = base64.b64encode(pcm_audio).decode()
    event = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{
                "type": "input_audio",
                "audio": pcm_base64,
            }]
        }
    }
    return json.dumps(event)

async def send_microphone_audio(ws, on_audio_complete):
    """Capture microphone audio, filter out silent chunks, and send it via WebSocket."""
    try:
        RATE = 24000  # 24kHz sampling rate
        CHANNELS = 1  # Mono audio
        CHUNK_SIZE = 4096  # Threshold for sending chunks of audio
        audio_data_accumulated = b""
        chunk_counter = 0  # Track sent chunks

        logger.info("Recording from microphone. Press Ctrl+C to stop.")

        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time, status):
            nonlocal audio_data_accumulated, chunk_counter
            if status:
                logger.error(f"Error: {status}")

            pcm_audio = (indata * 32767).astype('<i2').tobytes()

            if is_silent(pcm_audio):
                return

            audio_data_accumulated += pcm_audio

            if len(audio_data_accumulated) >= CHUNK_SIZE:
                logger.debug("Sending accumulated audio chunk.")
                audio_segment = AudioSegment.from_raw(
                    io.BytesIO(audio_data_accumulated),
                    sample_width=2, frame_rate=RATE, channels=CHANNELS
                )
                pcm_audio_resampled = audio_segment.set_frame_rate(RATE).set_channels(1).set_sample_width(2).raw_data
                encoded_chunk = base64.b64encode(pcm_audio_resampled).decode()

                event = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{
                            "type": "input_audio",
                            "audio": encoded_chunk
                        }]
                    }
                }
                asyncio.run_coroutine_threadsafe(ws.send(json.dumps(event)), loop)
                audio_data_accumulated = b""
                chunk_counter += 1

        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='float32', callback=audio_callback):
            while True:
                await asyncio.sleep(0.01)

    except Exception as e:
        logger.error(f"Error while sending microphone audio: {e}")

    # Notify when all chunks have been sent
    await on_audio_complete(chunk_counter)


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
