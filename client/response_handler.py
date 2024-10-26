import json
import uuid
import logging

# setup the logger
logger = logging.getLogger(__name__)

# Function to trigger the assistant's response after sending audio
async def trigger_response(ws, modalities, system_message, voice):
    """Trigger assistant response after all audio chunks are sent."""
    try:
        # get the event id
        event_id = f"event_{uuid.uuid4().hex}"

        # set the response data
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

        # check if we have audio in modalities
        if "audio" in modalities:
            response_data["response"]["voice"] = voice
            response_data["response"]["output_audio_format"] = "pcm16"

        # Log the response data to ensure it’s constructed properly
        logger.debug(f"Triggering response with event_id: {event_id}, modalities: {modalities}, system_message: {system_message}")

        # Send the response creation event
        await ws.send(json.dumps(response_data))
        logger.debug(f"Triggered response with event_id: {event_id}")

    except Exception as e:
        logger.error(f"Error while triggering response: {e}", exc_info=True)
