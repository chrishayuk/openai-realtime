import asyncio
import json
import logging
import threading
import audio_playback
from typing import List, Optional
from argument_parser import parse_arguments
from audio_decoder import decode_audio
from connection_handler import connect_to_server, close_connection
from message_handler import handle_message
from session import send_session_update
from audio_playback import FLUSH_COMMAND
from text_message_sender import send_text_message
from audio_message_sender import send_audio_file, send_microphone_audio

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Define distinct signals
SIGNAL_PROMPT = "PROMPT"
SIGNAL_EXIT = "EXIT"

# Define maximum retry attempts
MAX_RETRIES = 3

async def receive_messages(ws, streaming_mode, message_queue, modalities, state):
    """Receive messages from the server and handle text or audio playback."""
    # Accumulates full response for assistant
    transcript_buffer = ""  

    try:
        # loop through messages
        async for message in ws:
            # load the message
            response = json.loads(message)

            # get the message type
            message_type = response.get('type')

            # log some debug
            logger.debug(f"Received message of type: {message_type}")
            if message_type != "response.audio.delta":
                logger.debug(f"Full response: {response}")

            # Handle audio chunk processing
            if message_type == 'response.audio.delta':
                # get the audio delta
                await handle_audio_delta(response)
                continue

            # Handle text and audio transcript messages
            transcript_buffer, chunk = handle_message(response, transcript_buffer)

            # Handle streaming for text or audio transcript response
            if streaming_mode and chunk:
                # check we're in the response_started state
                if not state["response_started"]:
                    # Print "Assistant:" only once
                    print("Assistant: ", end="", flush=True)  
                    state["response_started"] = True

                # Print each text chunk or audio transcript chunk immediately
                if message_type in ['response.text.delta', 'response.audio_transcript.delta']:
                    print(chunk, end="", flush=True)

            # Handle conversation item creation
            if message_type == 'conversation.item.created':
                logger.debug("Conversation item created successfully.")
                continue

            # Handle final transcript from response.output_item.done
            if message_type == 'response.output_item.done':
                # get content
                content_list = response.get('item', {}).get('content', [])

                # loop through content
                for content in content_list:
                    # handle audio transcripts
                    if content.get('type') == 'audio' and 'transcript' in content:
                        # check if we're in response started state
                        if not state["response_started"]:
                            # Print "Assistant:" if not already printed
                            print("Assistant: ", end="", flush=True)  
                            state["response_started"] = True
                        
                        # print the transcript
                        print(content['transcript'], end="", flush=True)

            # When 'response.done' or 'response.audio_transcript.done' is received
            if message_type in ['response.done', 'response.audio_transcript.done']:
                logger.debug(f"Received {message_type} message.")
                response_status = response.get('response', {}).get('status')

                if response_status == 'failed':
                    await handle_error_and_retry(ws, message_queue, modalities, state)
                    continue

                await asyncio.to_thread(audio_playback.audio_queue.join)

                if state["exit_requested"]:
                    if "audio" in modalities:
                        audio_playback.enqueue_audio_chunk(FLUSH_COMMAND)
                        await asyncio.to_thread(audio_playback.audio_queue.join)

                if state["response_started"]:
                    print(f"\nYou: ", end="", flush=True)

                # put a signal prompt in the message queue
                await message_queue.put(SIGNAL_PROMPT)

                # clear response started
                state["response_started"] = False

                # clear the buffer
                transcript_buffer = ""

                # continue
                continue

    except Exception as e:
        logger.error(f"Error while receiving: {e}", exc_info=True)
        await message_queue.put(SIGNAL_EXIT)

async def handle_error_and_retry(ws, message_queue, modalities, state):
    """Automatically handle errors and retry sending after a short delay."""
    state["failure_count"] += 1

    # check for failures
    if state["failure_count"] <= MAX_RETRIES:
        backoff_time = 2 ** state["failure_count"]
        logger.warning(f"Retrying after {backoff_time} seconds (attempt {state['failure_count']}/{MAX_RETRIES})...")
        await asyncio.sleep(backoff_time)
        await message_queue.put(SIGNAL_PROMPT)
    else:
        logger.error("Maximum retry attempts reached. Exiting.")
        await message_queue.put(SIGNAL_EXIT)

async def handle_audio_delta(response: dict) -> None:
    """Handle audio chunk processing for 'response.audio.delta' messages."""
    # get the event id
    event_id = response.get('event_id')
    logger.debug(f"Received audio chunk: {event_id}")

    # get the chunk
    audio_chunk = response.get("delta", "")
    
    # check if we have a chunk
    if audio_chunk:
        # decode the audio
        decoded_audio = decode_audio(audio_chunk)

        # queue the audio for playback
        logger.debug(f"Decoded audio chunk size: {len(decoded_audio)} bytes")
        audio_playback.enqueue_audio_chunk(decoded_audio)


async def send_message(ws, modalities, message_queue, audio_source=None, system_message=None, voice=None):
    """Send user messages (text or audio) and trigger assistant responses."""
    try:
        # loop
        while True:
            # wait until we get a message response back from the message queue
            signal = await message_queue.get()
            logger.debug(f"send_message received signal: {signal}")

            # check if we have a signal prompt
            if signal == SIGNAL_PROMPT:
                # handle the prompt
                await handle_prompt(modalities, audio_source, ws, system_message, voice)
            elif signal == SIGNAL_EXIT:
                # exiting
                logger.info("Exiting application as per user request.")
                break
            else:
                # debug
                logger.debug(f"Received unexpected signal: {signal}")

    except asyncio.CancelledError:
        # message was cancelled
        logger.debug("send_message task was cancelled.")
    except Exception as e:
        # error
        logger.error(f"Error while sending message: {e}", exc_info=True)

        # send an exit signal to the message queue
        await message_queue.put(SIGNAL_EXIT)


async def handle_prompt(
    modalities: List[str],
    audio_source: Optional[str],
    ws,
    system_message: Optional[str],
    voice: Optional[str]
) -> None:
    """Handle the PROMPT signal to send user input as text or audio."""
    if "audio" in modalities and audio_source:
        if audio_source == "mic":
            response_done_event = asyncio.Event()
            logger.info("Recording from microphone. Speak into the microphone.")
            logger.debug("Audio stream started.")
            await send_microphone_audio(ws, modalities, system_message, voice, response_done_event)
            await response_done_event.wait()
        else:
            await send_audio_file(ws, audio_source)
    else:
        logger.debug("Prompting user for input")
        user_input = await asyncio.get_event_loop().run_in_executor(None, input, "You: ")

        logger.debug(f"User input received: {user_input}")

        if not user_input.strip():
            logger.debug("Empty user input, skipping.")
            return

        await send_text_message(ws, modalities, user_input, system_message, voice)


async def prompt_user_choice(failure_count: int) -> str:
    """Prompt the user to choose to retry or exit after an error."""
    loop = asyncio.get_event_loop()
    while True:
        choice = await loop.run_in_executor(None, input, f"Do you want to retry? (y/n): ")
        choice = choice.strip().lower()
        if choice in ['y', 'yes', 'r', 'retry']:
            logger.debug(f"User chose to retry. Attempt {failure_count}/{MAX_RETRIES}.")
            return 'retry'
        elif choice in ['n', 'no', 'e', 'exit']:
            logger.debug("User chose to exit.")
            return 'exit'
        else:
            print("Invalid choice. Please enter 'y' to retry or 'n' to exit.")
            logger.debug(f"Invalid user input for retry prompt: '{choice}'.")


async def clean_shutdown(playback_thread: threading.Thread, ws, modalities: List[str]) -> None:
    """Ensure a clean shutdown of playback thread and WebSocket connection."""
    logger.debug("Waiting for audio playback to finish.")
    await asyncio.to_thread(audio_playback.audio_queue.join)
    logger.debug("All audio chunks have been processed.")

    if "audio" in modalities:
        audio_playback.enqueue_audio_chunk(FLUSH_COMMAND)
        logger.debug("Enqueued FLUSH_COMMAND.")
        # Wait for FLUSH_COMMAND to be processed
        await asyncio.to_thread(audio_playback.audio_queue.join)
        logger.debug("Audio playback finished.")

    # Stop the playback thread
    audio_playback.stop_playback_thread(playback_thread)
    logger.debug("Playback thread has been stopped.")

    # Close the WebSocket connection
    await close_connection(ws)
    logger.debug("WebSocket connection closed.")


async def main(modalities, streaming_mode, audio_source=None, system_message=None, voice=None):
    """Main function to manage connection, message sending, and receiving."""
    # Start the playback thread and retrieve the thread instance
    playback_thread = audio_playback.start_playback_thread()
    logger.debug(f"Playback thread started: {playback_thread.is_alive()}")

    # Connect to the server
    ws = await connect_to_server()

    # Check if connection was successful
    if ws is None:
        logger.error("Failed to connect to server.")
        audio_playback.stop_playback_thread(playback_thread)
        return

    # Create a message queue
    message_queue = asyncio.Queue()
    logger.debug(f"Created message_queue: {message_queue}")

    # Initialize state dictionary
    state = {
        "response_started": False,    # Tracks if the assistant has started responding
        "exit_requested": False,      # Tracks if exit is requested to control FLUSH_COMMAND enqueuing
        "failure_count": 0            # Tracks the number of consecutive failures
    }

    try:
        # Send the session update
        await send_session_update(ws, modalities, voice, system_message)

        # Start chatting
        print("Start chatting! (Press Ctrl+C to exit)\n")
        print(f"\nYou: ", end="", flush=True)

        # Put SIGNAL_PROMPT in the queue to trigger the first send (prompt)
        await message_queue.put(SIGNAL_PROMPT)
        logger.debug("Initial signal put into message_queue")

        # Asynchronously receive and send messages
        receive_task = asyncio.create_task(receive_messages(ws, streaming_mode, message_queue, modalities, state))
        send_task = asyncio.create_task(send_message(ws, modalities, message_queue, audio_source, system_message, voice))

        # Wait for both tasks to complete
        await asyncio.gather(receive_task, send_task)
    except KeyboardInterrupt:
        logger.info("\nDisconnected from server by user.")
        state["exit_requested"] = True  # Indicate that exit is requested

        # Cancel the send task
        send_task.cancel()

        try:
            # Await the send_task to handle cancellation
            await send_task
        except asyncio.CancelledError:
            logger.debug("send_task has been cancelled.")
            pass

        # Allow receive_task to finish receiving any pending messages
        await receive_task
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # Perform clean shutdown
        await clean_shutdown(playback_thread, ws, modalities)


if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()

    # Set the modalities
    modalities = ["text", "audio"] if args.mode == "audio" else ["text"]

    # Streaming mode
    streaming_mode = not args.no_streaming

    # Optional audio source
    audio_source = args.audio_source if args.mode == "audio" else None

    # System prompt and voice from arguments
    system_message = args.system_prompt
    voice = args.voice

    try:
        # Run main
        asyncio.run(main(modalities, streaming_mode, audio_source, system_message, voice))
    except KeyboardInterrupt:
        # Disconnect
        logger.info("\nDisconnected from server by user.")
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"An error occurred: {e}", exc_info=True)
