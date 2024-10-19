import asyncio
import json
import uuid
import logging

logger = logging.getLogger(__name__)

async def send_conversation_item(ws, user_input):
    """
    Send user message as a conversation.item.create event.
    This function sends the user's input text as a WebSocket event with proper event formatting.
    """
    try:
        event_id = f"event_{uuid.uuid4().hex}"
        item_id = f"msg_{uuid.uuid4().hex[:28]}"

        # Create the event structure
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

        # Send the event over WebSocket
        await ws.send(json.dumps(event))
        logger.debug(f"Sent text message with event_id: {event_id}")

    except Exception as e:
        logger.error(f"Error while sending conversation item: {e}", exc_info=True)

async def trigger_text_response(ws, modalities, system_message, voice):
    """
    Trigger assistant response after sending the text message.
    This function creates a WebSocket event to trigger the assistant's response.
    """
    try:
        event_id = f"event_{uuid.uuid4().hex}"

        # Construct the response data structure
        response_data = {
            "event_id": event_id,
            "type": "response.create",
            "response": {
                "modalities": modalities,  # Modalities such as text or audio
                "instructions": system_message,  # System prompt passed along with user input
                "temperature": 0.7,
                "max_output_tokens": 1500  # Adjust this based on the length of responses needed
            }
        }

        # If audio is included, add voice parameters
        if "audio" in modalities:
            response_data["response"]["voice"] = voice
            response_data["response"]["output_audio_format"] = "pcm16"

        # Send the response creation event over WebSocket
        await ws.send(json.dumps(response_data))
        logger.debug(f"Triggered response with event_id: {event_id}")

    except Exception as e:
        logger.error(f"Error while triggering response: {e}", exc_info=True)

async def send_text_message(ws, modalities, user_input, system_message=None, voice=None):
    """Send text message as a conversation.item.create event."""
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
        # Send the event to the server
        await ws.send(json.dumps(event))
        logger.debug(f"Sent text message with event_id: {event_id}")
        
        # Trigger assistant response (if needed)
        await trigger_text_response(ws, modalities, system_message, voice)

    except Exception as e:
        logger.error(f"Error while sending text message: {e}", exc_info=True)
