import asyncio
import json
import uuid
import logging

logger = logging.getLogger(__name__)

async def trigger_response(ws, modalities, system_message, voice):
    """Trigger response generation based on the user message and mode."""
    try:
        event_id = f"event_{uuid.uuid4().hex}"
        response_data = {
            "event_id": event_id,
            "type": "response.create",
            "response": {
                "modalities": modalities, 
                "instructions": system_message,
                "temperature": 0.7,
                "max_output_tokens": 1500  # Adjust as needed
            }
        }

        if "audio" in modalities:
            response_data["response"]["voice"] = voice
            response_data["response"]["output_audio_format"] = "pcm16"

        await ws.send(json.dumps(response_data))
        logger.info(f"Triggered response with event_id: {event_id}")
    except Exception as e:
        logger.error(f"Error while triggering response: {e}", exc_info=True)
