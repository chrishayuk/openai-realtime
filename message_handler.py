# Function to handle different types of messages from the WebSocket
def handle_message(response, transcript_buffer):
    """Handle different types of messages from the server."""
    msg_type = response.get("type")
    
    # Handle text transcript deltas (chunked responses)
    if msg_type == "response.text.delta":
        delta = response.get("delta", "")
        transcript_buffer += delta
        return transcript_buffer, delta  # Return both the buffer and the chunk

    # Final text transcript is received
    elif msg_type == "response.text.done":
        final_chunk = transcript_buffer
        return "", final_chunk  # Clear the buffer after final text is handled

    # Handle audio transcript deltas (chunked audio responses)
    elif msg_type == "response.audio_transcript.delta":
        delta = response.get("transcript", "")
        transcript_buffer += delta
        return transcript_buffer, delta  # Return both the buffer and the chunk

    # Final audio transcript is received
    elif msg_type == "response.audio_transcript.done":
        final_chunk = transcript_buffer
        return "", final_chunk  # Clear the buffer after final transcript

    # Handle response completion
    elif msg_type == "response.done":
        return transcript_buffer, None  # No chunk, just return the buffer

    # Handle audio chunks
    elif msg_type == "response.audio.delta":
        audio_chunk = response.get("delta", "")
        return transcript_buffer, audio_chunk  # Return the buffer and the audio chunk

    # Suppress unnecessary message types
    ignored_message_types = [
        "session.created", "session.updated", "response.created", 
        "rate_limits.updated", "response.output_item.added", 
        "conversation.item.created", "response.content_part.added", 
        "response.output_item.done"
    ]
    
    if msg_type in ignored_message_types:
        return transcript_buffer, None  # Ignore these message types silently

    # Return buffer and None for unhandled message types
    return transcript_buffer, None
