import asyncio
import json
import uuid
import logging
import base64
import sounddevice as sd
from audio_processing import audio_to_item_create_event, is_silent
from pydub import AudioSegment

logger = logging.getLogger(__name__)

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
            logger.info(f"Sent audio file: {file_path}")
    except Exception as e:
        logger.error(f"Error while sending audio file: {e}", exc_info=True)

# Function to send microphone audio to the server in real-time
async def send_microphone_audio(ws, modalities, system_message, voice):
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
        chunk_counter = 0  # Number of chunks sent

        logger.info("Recording from microphone. Speak into the microphone.")

        loop = asyncio.get_running_loop()

        # Audio callback for real-time processing
        def audio_callback(indata, frames, time, status):
            nonlocal audio_data_accumulated, silence_duration, speaking, chunk_counter
            try:
                if status:
                    logger.error(f"Error: {status}")

                # Convert the audio to PCM16 format
                pcm_audio = (indata * 32767).astype('<i2').tobytes()

                if is_silent(pcm_audio, threshold=SILENCE_THRESHOLD):
                    silence_duration += frames / RATE

                    # If user was speaking and silence exceeds threshold, send accumulated audio
                    if speaking and silence_duration >= MAX_SILENCE_DURATION:
                        logger.info("End of speech detected. Sending accumulated audio.")
                        if audio_data_accumulated:
                            logger.debug(f"Sending {len(audio_data_accumulated)} bytes of audio.")
                            send_audio_chunk(loop, ws, audio_data_accumulated, RATE, CHANNELS)
                            chunk_counter += 1
                            audio_data_accumulated = b""  # Reset buffer
                        speaking = False
                        silence_duration = 0.0  # Reset silence duration

                        # Trigger response after sending audio
                        asyncio.run_coroutine_threadsafe(
                            trigger_response(ws, modalities, system_message, voice), loop
                        )
                else:
                    # Accumulate audio when speaking
                    silence_duration = 0.0
                    audio_data_accumulated += pcm_audio
                    speaking = True
                    logger.debug(f"Accumulating audio. Buffer size: {len(audio_data_accumulated)} bytes.")

            except Exception as e:
                logger.error(f"Error in audio_callback: {e}", exc_info=True)

        # Start the audio input stream
        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='float32', callback=audio_callback, blocksize=CHUNK_SIZE):
            logger.debug("Audio stream started.")
            while True:
                await asyncio.sleep(0.1)  # Keep the stream running

    except Exception as e:
        logger.error(f"Error while sending microphone audio: {e}", exc_info=True)

# Function to send the accumulated audio chunk
def send_audio_chunk(loop, ws, audio_data_accumulated, rate, channels):
    """Send the accumulated audio chunk via WebSocket."""
    try:
        # Convert audio data to PCM16 and encode in base64
        audio_segment = AudioSegment(
            data=audio_data_accumulated,
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
        future = asyncio.run_coroutine_threadsafe(ws.send(json.dumps(event)), loop)
        future.result()  # Ensure send completes before continuing
        logger.debug(f"Audio chunk of size {len(audio_data_accumulated)} bytes sent successfully.")

    except Exception as e:
        logger.error(f"Error sending audio chunk: {e}", exc_info=True)

# Function to trigger the assistant's response after sending audio
async def trigger_response(ws, modalities, system_message, voice):
    """Trigger assistant response after all audio chunks are sent."""
    try:
        event_id = f"event_{uuid.uuid4().hex}"
        response_data = {
            "event_id": event_id,
            "type": "response.create",
            "response": {
                "modalities": ['audio'],
                "instructions": system_message,
                "temperature": 0.7,
                "max_output_tokens": 1500  # Adjust as needed
            }
        }

        response_data["response"]["voice"] = voice
        response_data["response"]["output_audio_format"] = "pcm16"

        # Log the response data to ensure it’s constructed properly
        logger.info(f"Triggering response with event_id: {event_id}, modalities: {modalities}, system_message: {system_message}")

        # Send the response creation event
        await ws.send(json.dumps(response_data))
        logger.info(f"Triggered response with event_id: {event_id}")

    except Exception as e:
        logger.error(f"Error while triggering response: {e}", exc_info=True)
