import base64
import io
import json
import logging
import numpy as np
from pydub import AudioSegment

# Initialize logging
logger = logging.getLogger(__name__)

# Function to convert audio bytes to conversation.item.create event format
def audio_to_item_create_event(audio_bytes: bytes) -> str:
    """
    Convert audio bytes to conversation.item.create event format.
    This converts raw audio bytes to base64 encoded PCM16 data at 24kHz, mono.
    """
    try:
        # Load the audio from the byte stream and resample it to 24kHz mono PCM16
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2).raw_data
        pcm_base64 = base64.b64encode(pcm_audio).decode()

        # Construct the WebSocket event
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
    except Exception as e:
        logger.error(f"Error creating audio event: {e}")
        return None

# Function to check if an audio chunk is mostly silent based on its RMS
def is_silent(pcm_audio, threshold=100):
    """Check if the audio data is mostly silence based on RMS."""
    try:
        # Get audio data from buffer
        audio_data = np.frombuffer(pcm_audio, dtype=np.int16)

        # Ensure we have data
        if len(audio_data) == 0:
            return True

        # Check for invalid values or out-of-range audio samples
        if np.all(audio_data == 0) or np.any(np.isnan(audio_data)) or np.max(np.abs(audio_data)) > 32767:
            return True

        # Calculate RMS (Root Mean Square)
        with np.errstate(invalid='ignore'):
            rms = np.sqrt(np.mean(np.square(audio_data)))

        return rms < threshold  # Return True if RMS is below threshold (indicating silence)
    except (ValueError, OverflowError) as e:
        logger.error(f"Error processing audio data for RMS: {e}")
        return True
