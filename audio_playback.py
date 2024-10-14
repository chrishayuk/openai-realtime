# audio_playback.py
import threading
import queue
import time
import pyaudio
import logging

# Initialize logging
logger = logging.getLogger(__name__)

# Define a unique sentinel object for the FLUSH command
FLUSH_COMMAND = object()

# Audio queue for thread-safe communication
audio_queue = queue.Queue()

# Event to signal the playback thread to stop
stop_event = threading.Event()

# Event to signal that playback of the current response is complete
playback_complete_event = threading.Event()

# Buffering configuration
BUFFER_THRESHOLD = 5000 
MAX_WAIT_TIME = 0.5

# PyAudio parameters
SAMPLE_RATE = 24000
CHANNELS = 1
FORMAT = pyaudio.paInt16

def audio_playback():
    """
    Dedicated thread function for audio playback.
    """
    # Initialize
    logger.debug("Playback thread started.")
    buffer = bytearray()
    last_play_time = time.time()
    stream = None  

    try:
        # initialize pyaudio
        p = pyaudio.PyAudio()
        logger.debug("PyAudio initialized.")

        # open the stream
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE, output=True)
        logger.debug("PyAudio stream opened.")
    except Exception as e:
        # failed to open the stream
        logger.error(f"Failed to initialize PyAudio: {e}", exc_info=True)
        
        # playback complete
        playback_complete_event.set()
        return

    try:
        # loop while we don't have a stop event
        while not stop_event.is_set():
            try:
                # Wait for an audio chunk with a timeout
                audio_chunk = audio_queue.get(timeout=0.1)
                logger.debug("Got an item from the queue.")
            except queue.Empty:
                # check if we have anything in the buffer
                if buffer:
                    # play whatever is in the buffer
                    logger.debug(f"Playing remaining {len(buffer)} bytes of audio (queue empty).")
                    stream.write(bytes(buffer))

                    # clear the buffer
                    buffer.clear()
                    last_play_time = time.time()
                continue

            # check if we have a chunk
            if audio_chunk is None:
                # shutdown
                logger.debug("Received shutdown signal.")

                # Mark the queue task as done
                audio_queue.task_done()
                break

            # check we if we have the flush command
            if audio_chunk is FLUSH_COMMAND:
                # check if anything in the buffer
                if buffer:
                    # flush the buffer, and play remaining audio
                    logger.debug(f"Flushing buffer on FLUSH_COMMAND with {len(buffer)} bytes.")
                    stream.write(bytes(buffer))
                    buffer.clear()
                    last_play_time = time.time()

                # playback complete
                logger.debug("Buffer is empty upon receiving FLUSH_COMMAND.")
                playback_complete_event.set()

                # Mark the queue task as done
                audio_queue.task_done()
                continue

            # Process and play the audio chunk
            buffer.extend(audio_chunk)
            current_time = time.time()

            # check if we have an audio to kick off playback
            if len(buffer) >= BUFFER_THRESHOLD or (current_time - last_play_time) >= MAX_WAIT_TIME:
                logger.debug(f"Playing {len(buffer)} bytes of audio.")
                stream.write(bytes(buffer))
                buffer.clear()
                last_play_time = current_time

            # processed
            logger.debug(f"Processed audio chunk, {audio_queue.unfinished_tasks - 1} remaining chunks.")

            # Mark the queue task as done
            audio_queue.task_done()

        # Play any remaining audio when exiting
        if buffer:
            logger.debug(f"Playing remaining {len(buffer)} bytes of audio before exiting.")
            stream.write(bytes(buffer))

    except Exception as e:
        # log the error
        logger.error(f"Exception in playback thread: {e}", exc_info=True)
    finally:
        if stream is not None:
            try:
                # check if the stream is stopped
                if not stream.is_stopped():
                    # stop the stream
                    stream.stop_stream()

                # close the stream
                stream.close()
            except Exception as e:
                # log the error
                logger.warning(f"Error closing stream: {e}")
            p.terminate()
        else:
            # debug
            logger.debug("Stream was not initialized.")
        logger.debug("Playback thread terminated.")
        playback_complete_event.set()

def start_playback_thread():
    """
    Starts the dedicated playback thread.
    """
    # Clear any previous playback completion event
    playback_complete_event.clear()
    stop_event.clear()
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
    if audio_chunk is FLUSH_COMMAND:
        logger.debug("Enqueued FLUSH_COMMAND")
    elif audio_chunk is None:
        logger.debug("Enqueued shutdown signal")
    else:
        logger.debug(f"Enqueued audio chunk, {audio_queue.unfinished_tasks} pending chunks.")

def wait_for_playback_finish():
    """
    Waits for all audio chunks to be played back.
    """
    logger.debug("Waiting for playback to finish.")

    # Wait until all items in the queue have been processed
    audio_queue.join()

    # Wait for the playback completion event
    playback_complete_event.wait()
    logger.debug("Playback finished.")

    # Clear the event for the next use
    playback_complete_event.clear()
