import asyncio
import json
import logging
import audio_playback
from argument_parser import parse_arguments
from audio_decoder import decode_audio
from session import send_session_update
from message_handler import handle_message
from connection_handler import connect_to_server, close_connection
from audio_playback import FLUSH_COMMAND
from text_message_sender import send_text_message
from audio_message_sender import send_audio_file, send_microphone_audio, create_on_audio_complete

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def receive_messages(ws, streaming_mode, message_queue, modalities):
    """Receive messages from the server and handle text or audio playback."""
    transcript_buffer = ""  # Accumulates full response for assistant
    response_started = False  # Tracks whether the assistant has started responding

    try:
        async for message in ws:
            response = json.loads(message)
            message_type = response.get('type')

            logger.debug(f"Received message of type: {message_type}")

            # Handle audio chunk processing
            if message_type == 'response.audio.delta':
                event_id = response.get('event_id')
                logger.debug(f"Received audio chunk: {event_id}")

                audio_chunk = response.get("delta", "")

                if audio_chunk:
                    # Correctly decode base64-encoded audio chunk
                    decoded_audio = decode_audio(audio_chunk)
                    logger.debug(f"Decoded audio chunk size: {len(decoded_audio)} bytes")

                    # Queue the chunk for audio playback
                    audio_playback.enqueue_audio_chunk(decoded_audio)
                continue

            # Handle text and audio transcript messages
            transcript_buffer, chunk = handle_message(response, transcript_buffer)

            # Handle streaming for text or audio transcript response
            if streaming_mode and chunk:
                if not response_started:
                    print("Assistant: ", end="", flush=True)  # Print "Assistant:" only once
                    response_started = True

                # Print each text chunk or audio transcript chunk immediately
                if message_type in ['response.text.delta', 'response.audio_transcript.delta']:
                    print(chunk, end="", flush=True)

            # Handle final transcript from response.output_item.done
            if message_type == 'response.output_item.done':
                content_list = response.get('item', {}).get('content', [])
                for content in content_list:
                    if content.get('type') == 'audio' and 'transcript' in content:
                        if not response_started:
                            print("Assistant: ", end="", flush=True)  # Print "Assistant:" if not already printed
                            response_started = True
                        print(content['transcript'], end="", flush=True)

            # When 'response.done' or 'response.audio_transcript.done' is received
            if message_type in ['response.done', 'response.audio_transcript.done']:
                logger.debug(f"Received {message_type} message.")
                logger.debug(f"Waiting for {audio_playback.audio_queue.unfinished_tasks} audio chunks to finish...")

                # Wait for audio chunks to finish if any
                while audio_playback.audio_queue.unfinished_tasks > 0:
                    await asyncio.sleep(0.1)  # Small delay to wait for chunks to be processed

                logger.debug("All audio chunks processed.")

                # Send the flush command only after all audio chunks are processed
                if "audio" in modalities:
                    audio_playback.enqueue_audio_chunk(FLUSH_COMMAND)
                    logger.debug("Enqueued FLUSH_COMMAND.")
                    audio_playback.wait_for_playback_finish()
                    logger.debug("Audio playback finished.")

                # Now prompt for the next input, but only if the assistant has finished responding
                if response_started:
                    print(f"\nYou: ", end="", flush=True)


                # Add to the message queue for the next input
                await message_queue.put(None)
                response_started = False  # Reset after assistant finishes
                transcript_buffer = ""
                continue

    except Exception as e:
        logger.error(f"Error while receiving: {e}", exc_info=True)


async def send_message(ws, modalities, message_queue, audio_source=None, system_message=None, voice=None):
    """Send user messages (text or audio) and trigger assistant responses."""
    try:
        while True:
            # Handle audio mode
            if "audio" in modalities and audio_source:
                if audio_source == "mic":
                    # Capture and send microphone audio
                    await send_microphone_audio(ws, create_on_audio_complete(ws, modalities, system_message, voice))
                else:
                    # Send audio from a file
                    await send_audio_file(ws, audio_source)
                    # Trigger assistant response after audio
                    await create_on_audio_complete(ws, modalities, system_message, voice)(1)  # Assuming 1 chunk for file
            else:
                # Handle text input mode (no "You:" prompt here)
                user_input = await asyncio.get_event_loop().run_in_executor(None, input)

                # Skip empty input
                if not user_input.strip():
                    logger.debug("Empty user input, skipping.")
                    continue

                # Send text message directly
                await send_text_message(ws, modalities, user_input, system_message, voice)

    except Exception as e:
        logger.error(f"Error while sending message: {e}", exc_info=True)

async def main(modalities, streaming_mode, audio_source=None, system_message=None, voice=None):
    # Start the playback thread
    playback_thread = audio_playback.start_playback_thread()
    logger.debug(f"Playback thread started: {playback_thread.is_alive()}")

    # Connect to the server
    ws = await connect_to_server()

    # Check if connection was successful
    if ws is None:
        print("Failed to connect to server.")
        audio_playback.stop_playback_thread(playback_thread)
        return

    # Create a message queue
    message_queue = asyncio.Queue()

    try:
        # Send the session update
        await send_session_update(ws, modalities, voice, system_message)

        # Start chatting
        print("Start chatting! (Press Ctrl+C to exit)\n")
        print(f"\nYou: ", end="", flush=True)

        # Put None in the queue to trigger the first send
        await message_queue.put(None)

        # Asynchronously receive and send messages
        receive_task = asyncio.create_task(receive_messages(ws, streaming_mode, message_queue, modalities))
        send_task = asyncio.create_task(send_message(ws, modalities, message_queue, audio_source, system_message, voice))

        # Wait for both tasks to complete
        await asyncio.gather(receive_task, send_task)
    except KeyboardInterrupt:
        print("\nDisconnected from server by user.")

        # Cancel the send task
        send_task.cancel()

        try:
            # call send task
            await send_task
        except asyncio.CancelledError:
            pass

        # Allow receive_task to finish receiving any pending messages
        await receive_task
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # Ensure all audio has been played
        logger.debug("Waiting for audio playback to finish.")
        audio_playback.wait_for_playback_finish()
        logger.debug(f"Playback thread alive after playback: {playback_thread.is_alive()}")

        # Stop the playback thread
        audio_playback.stop_playback_thread(playback_thread)
        logger.debug(f"Playback thread stopped: {playback_thread.is_alive()}")

        # Close the WebSocket connection
        await close_connection(ws)


if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()

    # Set the modalities
    modalities = ["text", "audio"] if args.mode == "audio" else ["text"]

    # No streaming
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
        print("\nDisconnected from server by user.")
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"An error occurred: {e}", exc_info=True)
