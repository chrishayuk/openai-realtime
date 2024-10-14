# message_sender.py
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
    except Exception as e:
        print(f"Error while sending conversation item: {e}")

async def trigger_response(ws, modalities, system_message, voice):
    """Trigger response generation based on the user message and mode."""
    try:
        # Set the event ID
        event_id = f"event_{uuid.uuid4().hex}"

        # Set the response data
        response_data = {
            "event_id": event_id,
            "type": "response.create",
            "response": {
                "modalities": modalities,  # Respect text or text+audio modes
                "instructions": system_message,
                "temperature": 0.7,
                "max_output_tokens": 1500  # Adjusted for longer responses
            }
        }

        # If audio is included, add voice and output_audio_format
        if "audio" in modalities:
            response_data["response"]["voice"] = voice
            response_data["response"]["output_audio_format"] = "pcm16"

        # Send the response create event
        await ws.send(json.dumps(response_data))
    except Exception as e:
        # Error
        logger.error(f"Error while triggering response: {e}", exc_info=True)


async def send_message(ws, modalities, message_queue, audio_source=None, system_message=None, voice=None):
    """Send user messages or audio interactively and trigger assistant responses."""
    try:
        while True:
            await message_queue.get()

            # Handle audio mode
            if "audio" in modalities and audio_source:
                # If microphone or file is specified, handle accordingly
                if audio_source == "mic":
                    await send_microphone_audio(ws)  # Send microphone audio
                else:
                    await send_audio_file(ws, audio_source)  # Send audio from file
            else:
                # Handle text mode, even in audio mode when no audio input is specified
                user_input = await asyncio.get_event_loop().run_in_executor(None, input, "")

                if not user_input.strip():
                    continue

                # Send text conversation item
                await send_conversation_item(ws, user_input)

            # Trigger response from the server
            await trigger_response(ws, modalities, system_message, voice)
    except KeyboardInterrupt:
        print("\nExiting chat...")
    except Exception as e:
        logger.error(f"Error while sending message: {e}", exc_info=True)