# audio_playback.py
import threading
import queue
import time
import pyaudio
import logging

# Initialize logging
logger = logging.getLogger(__name__)

# Audio queue for thread-safe communication
audio_queue = queue.Queue()

# Event to signal the playback thread to stop
stop_event = threading.Event()

# Buffering configuration
BUFFER_THRESHOLD = 5000  # Adjusted buffer threshold for longer audio
MAX_WAIT_TIME = 0.5       # Adjusted max wait time to allow more data to arrive

# PyAudio parameters
SAMPLE_RATE = 24000  # Ensure this matches your audio data
CHANNELS = 1
FORMAT = pyaudio.paInt16  # 16-bit PCM audio

def audio_playback():
    """
    Dedicated thread function for audio playback.
    """
    logger.debug("Playback thread started.")
    buffer = bytearray()
    last_play_time = time.time()

    # Initialize PyAudio and the stream
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE, output=True)

    try:
        while not stop_event.is_set():
            try:
                # Wait for an audio chunk with a timeout
                audio_chunk = audio_queue.get(timeout=0.1)
                if audio_chunk is None:
                    # Sentinel value received, exit the loop
                    logger.debug("Playback thread received shutdown signal.")
                    break

                buffer.extend(audio_chunk)
                current_time = time.time()

                # Play the buffer when it's large enough or the wait time is reached
                if len(buffer) >= BUFFER_THRESHOLD or (current_time - last_play_time) >= MAX_WAIT_TIME:
                    logger.debug(f"Playing {len(buffer)} bytes of audio.")
                    stream.write(bytes(buffer))
                    buffer.clear()
                    last_play_time = current_time

                audio_queue.task_done()

            except queue.Empty:
                # Check if we need to flush the buffer
                current_time = time.time()
                if buffer and (current_time - last_play_time) >= MAX_WAIT_TIME:
                    logger.debug(f"Playing remaining {len(buffer)} bytes of audio (timeout).")
                    stream.write(bytes(buffer))
                    buffer.clear()
                    last_play_time = current_time
                continue

            except Exception as e:
                logger.error(f"Error during audio playback: {e}")
                continue  # Continue processing next chunk

        # Play any remaining audio when exiting
        if buffer:
            logger.debug(f"Playing remaining {len(buffer)} bytes of audio.")
            stream.write(bytes(buffer))

    except Exception as e:
        logger.error(f"Exception in playback thread: {e}")
    finally:
        # Close the stream and PyAudio
        stream.stop_stream()
        stream.close()
        p.terminate()
        logger.debug("Playback thread terminated.")

def start_playback_thread():
    """
    Starts the dedicated playback thread.
    """
    playback_thread = threading.Thread(target=audio_playback, daemon=True)
    playback_thread.start()
    return playback_thread

def stop_playback_thread(playback_thread):
    """
    Signals the playback thread to stop and waits for it to finish.
    """
    stop_event.set()
    audio_queue.put(None)  # Sentinel value to unblock the queue.get()
    playback_thread.join()
    logger.debug("Playback thread successfully stopped.")

def enqueue_audio_chunk(audio_chunk):
    """
    Enqueues an audio chunk for playback.
    """
    audio_queue.put(audio_chunk)
    logger.debug(f"Enqueued audio chunk, Queue size: {audio_queue.qsize()}")

def wait_for_playback_finish():
    """
    Waits for all audio chunks to be played back.
    """
    audio_queue.join()
    logger.debug("All audio playback completed.")
