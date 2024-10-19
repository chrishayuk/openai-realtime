import asyncio
import json
import uuid
import logging
from audio_message_sender import send_audio_file, send_microphone_audio

logger = logging.getLogger(__name__)

# Function to send user message as conversation.item.create
async def send_conversation_item(ws, user_input):
    """Send user message as a conversation.item.create event."""
    try:
        event_id = f"event_{uuid.uuid4().hex}"
        item_id = f"msg_{uuid.uuid4().hex[:28]}"
        event = {
            "event_id": event_id,
            "type": "conversation.item.create",
            "previous_item_id": None,
            "item": {
                "id": item_id,
                "type": "message",
                "status": "completed",
                "role": "user",
                "content": [{"type": "input_text", "text": user_input}]
            }
        }
        await ws.send(json.dumps(event))
        logger.info(f"Sent text message with event_id: {event_id}")
    except Exception as e:
        logger.error(f"Error while sending conversation item: {e}", exc_info=True)

# Function to trigger assistant response
async def trigger_response(ws, modalities, system_message, voice):
    """Trigger response generation based on the user message and mode."""
    try:
        event_id = f"event_{uuid.uuid4().hex}"

        # Set the response data
        response_data = {
            "event_id": event_id,
            "type": "response.create",
            "response": {
                "modalities": modalities,  # Respect text or text+audio modes
                "instructions": system_message,
                "temperature": 0.7,
                "max_output_tokens": 1500  # Adjust for longer responses
            }
        }

        # If audio is included, add voice and output_audio_format
        if "audio" in modalities:
            response_data["response"]["voice"] = voice
            response_data["response"]["output_audio_format"] = "pcm16"

        # Send the response create event
        await ws.send(json.dumps(response_data))
        logger.info(f"Triggered response with event_id: {event_id}")
    except Exception as e:
        logger.error(f"Error while triggering response: {e}", exc_info=True)

# Callback function when all audio chunks have been sent
async def on_audio_complete(ws, modalities, system_message, voice, chunk_counter):
    """Callback to trigger response creation after all audio chunks have been sent."""
    logger.info(f"All {chunk_counter} audio chunks sent, now triggering response.")
    await trigger_response(ws, modalities, system_message, voice)

# Main function to handle sending text/audio messages and triggering responses
async def send_message(ws, modalities, message_queue, audio_source=None, system_message=None, voice=None):
    """Send user messages or audio interactively and trigger assistant responses."""
    try:
        while True:
            # Wait for an item from the message queue
            logger.debug("Waiting for a message from the queue...")
            await message_queue.get()
            logger.debug("Received a message from the queue.")

            # Handle audio mode
            if "audio" in modalities and audio_source:
                logger.debug(f"Audio mode active with source: {audio_source}")

                # Callback for audio completion
                async def on_audio_complete(chunk_counter):
                    logger.info(f"All {chunk_counter} chunks sent, triggering response.")
                    await trigger_response(ws, modalities, system_message, voice)

                # If microphone or file is specified, handle accordingly
                if audio_source == "mic":
                    try:
                        await send_microphone_audio(ws, on_audio_complete)  # Pass the completion callback
                        logger.info("Sent microphone audio.")
                    except Exception as e:
                        logger.error(f"Error while sending microphone audio: {e}", exc_info=True)
                else:
                    try:
                        await send_audio_file(ws, audio_source)  # Send audio from file
                        await on_audio_complete(1)  # Call callback assuming 1 chunk for file
                        logger.info(f"Sent audio file: {audio_source}")
                    except Exception as e:
                        logger.error(f"Error while sending audio file: {e}", exc_info=True)

            else:
                # Handle text mode, even in audio mode when no audio input is specified
                logger.debug("Text mode active, waiting for user input.")
                user_input = await asyncio.get_event_loop().run_in_executor(None, input, "")

                # Skip empty input
                if not user_input.strip():
                    logger.debug("Empty user input, skipping.")
                    continue

                # Send text conversation item
                logger.debug(f"Sending text message: {user_input}")
                await send_conversation_item(ws, user_input)

                # Trigger response from the server after sending the message
                logger.debug("Triggering response from server after text input.")
                await trigger_response(ws, modalities, system_message, voice)

    except KeyboardInterrupt:
        print("\nExiting chat...")
    except Exception as e:
        logger.error(f"Error while sending message: {e}", exc_info=True)
