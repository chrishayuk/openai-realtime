import asyncio
import json
import logging
import base64
import sounddevice as sd
from pydub import AudioSegment
from client.response_handler import trigger_response
from client.audio.audio_processing import audio_to_item_create_event, is_silent

logger = logging.getLogger(__name__)

# Function to send microphone audio to the server in real-time
async def send_microphone_audio(ws, modalities, system_message, voice, response_done_event):
    """
    Capture and send microphone audio in real-time to the server.
    Trigger the assistant response after sending the last audio chunk.
    """
    try:
        RATE = 24000  # 24kHz sampling rate
        CHANNELS = 1  # Mono audio
        CHUNK_SIZE = 1024  # Frames per chunk
        MAX_SILENCE_DURATION = 1.0  # Maximum silence duration in seconds
        SILENCE_THRESHOLD = 100  # RMS threshold for silence

        audio_data_accumulated = b""  # Accumulated audio data
        silence_duration = 0.0  # Duration of consecutive silence
        speaking = False  # Whether the user is speaking
        audio_sent = False  # Flag to ensure audio is only sent once after silence

        logger.debug("Recording from microphone. Speak into the microphone.")

        # Get the current event loop at the start and pass it to the callback
        loop = asyncio.get_running_loop()

        # Define an async function for processing and sending audio chunks
        async def process_audio_chunk(pcm_audio):
            nonlocal audio_data_accumulated, silence_duration, speaking, audio_sent

            if is_silent(pcm_audio, threshold=SILENCE_THRESHOLD):
                silence_duration += len(pcm_audio) / (RATE * 2)  # Adjust for the size of PCM16

                # If user was speaking and silence exceeds threshold, send accumulated audio
                if speaking and silence_duration >= MAX_SILENCE_DURATION and not audio_sent:
                    logger.debug("End of speech detected. Sending accumulated audio.")
                    if audio_data_accumulated:
                        logger.debug(f"Sending {len(audio_data_accumulated)} bytes of audio.")
                        await send_audio_chunk(ws, audio_data_accumulated, RATE, CHANNELS)
                        audio_data_accumulated = b""  # Reset buffer after sending
                        silence_duration = 0.0  # Reset silence duration
                        speaking = False  # Reset speaking status
                        audio_sent = True  # Set flag to avoid sending repeatedly

                        # Trigger response after sending audio
                        await trigger_response(ws, modalities, system_message, voice)

                        # Signal that the response is done
                        response_done_event.set()
            else:
                # Reset flags when new speech is detected
                silence_duration = 0.0  # Reset silence duration if audio is detected
                audio_data_accumulated += pcm_audio
                speaking = True
                if audio_sent:
                    # New speech detected after sending audio
                    audio_sent = False
                logger.debug(f"Accumulating audio. Buffer size: {len(audio_data_accumulated)} bytes.")

        # Audio callback for real-time processing
        def audio_callback(indata, frames, time, status):
            try:
                if status:
                    logger.error(f"Error: {status}")

                # Convert the audio to PCM16 format
                pcm_audio = (indata * 32767).astype('<i2').tobytes()

                # Use the main event loop to process the audio chunk asynchronously
                asyncio.run_coroutine_threadsafe(process_audio_chunk(pcm_audio), loop)

            except Exception as e:
                logger.error(f"Error in audio_callback: {e}", exc_info=True)

        # Start the audio input stream
        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='float32',
                            callback=audio_callback, blocksize=CHUNK_SIZE):
            logger.debug("Audio stream started.")
            while not response_done_event.is_set():
                await asyncio.sleep(0.1)  # Keep the stream running

    except Exception as e:
        logger.error(f"Error while sending microphone audio: {e}", exc_info=True)


# Function to send the accumulated audio chunk
async def send_audio_chunk(ws, audio_data, rate, channels):
    """Send the accumulated audio chunk via WebSocket."""
    try:
        # Convert audio data to PCM16 and encode in base64
        audio_segment = AudioSegment(
            data=audio_data,
            sample_width=2,
            frame_rate=rate,
            channels=channels
        )
        pcm_audio_resampled = audio_segment.set_frame_rate(rate).set_channels(1).set_sample_width(2).raw_data
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

        # Send the audio chunk asynchronously
        await ws.send(json.dumps(event))
        logger.debug(f"Audio chunk of size {len(audio_data)} bytes sent successfully.")

    except Exception as e:
        logger.error(f"Error sending audio chunk: {e}", exc_info=True)


# Function to send audio from a file as a conversation item
async def send_audio_file(ws, file_path):
    """Send audio from a file to the WebSocket."""
    try:
        # Read the file as bytes
        with open(file_path, 'rb') as f:
            audio_bytes = f.read()

        # Convert audio bytes into a WebSocket event
        event = audio_to_item_create_event(audio_bytes)

        if event:
            # Send the event over WebSocket
            await ws.send(event)
            logger.debug(f"Sent audio file: {file_path}")
    except Exception as e:
        logger.error(f"Error while sending audio file: {e}", exc_info=True)
