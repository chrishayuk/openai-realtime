# message_handler.py

# Function to handle different types of messages from the WebSocket
def handle_message(response, transcript_buffer):
    """Handle different types of messages from the server."""
    msg_type = response.get("type")
    
    # Handle audio transcript deltas
    if msg_type == "response.audio_transcript.delta":
        delta = response.get("transcript", "")
        transcript_buffer += delta
        print(f"Partial Transcript: {transcript_buffer}")
        return transcript_buffer

    # Final audio transcript is received
    elif msg_type == "response.audio_transcript.done":
        print(f"Final Transcript: {transcript_buffer}")
        return ""

    # Handle audio delta (audio data chunks)
    elif msg_type == "response.audio.delta":
        audio_chunk = response.get("delta", "")
        print(f"Audio chunk received: {len(audio_chunk)} bytes")
        return transcript_buffer

    # Handle text transcript deltas
    elif msg_type == "response.text.delta":
        delta = response.get("delta", "")
        transcript_buffer += delta
        print(f"Partial Text: {transcript_buffer}")
        return transcript_buffer

    # Final text transcript is received
    elif msg_type == "response.text.done":
        print(f"Final Text: {transcript_buffer}")
        return ""

    # Handle response completion
    elif msg_type == "response.done":
        print("\n[Response complete]\n")
        return transcript_buffer

    # Handle content part done (for audio or transcript)
    elif msg_type == "response.content_part.done":
        part = response.get("part", {})
        if part.get("type") == "audio" and "transcript" in part:
            print(f"Transcript (from content part): {part['transcript']}")
        return transcript_buffer

    # Suppress unnecessary message types
    ignored_message_types = [
        "session.created", "session.updated", "response.created", 
        "rate_limits.updated", "response.output_item.added", 
        "conversation.item.created", "response.content_part.added", 
        "response.output_item.done"
    ]
    
    if msg_type in ignored_message_types:
        return transcript_buffer  # Ignore these message types silently

    # Log unhandled message types
    print(f"Unhandled message type: {msg_type}")
    return transcript_buffer
