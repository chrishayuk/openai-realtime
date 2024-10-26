# session.py
import json
import logging

# Initialize logging
logger = logging.getLogger(__name__)

# Function to send session update
async def send_session_update(ws, modalities, voice, system_message):
    """Send session update to WebSocket Server"""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "instructions": system_message,
            "modalities": modalities,
            "temperature": 0.8,
        }
    }

    # Add audio-related fields only if "audio" is in modalities
    if "audio" in modalities:
        session_update["session"]["input_audio_format"] = "pcm16"
        session_update["session"]["output_audio_format"] = "pcm16"
        session_update["session"]["voice"] = voice

    # debug
    logger.debug("Sending session update")

    # send to the web socket server
    await ws.send(json.dumps(session_update))
