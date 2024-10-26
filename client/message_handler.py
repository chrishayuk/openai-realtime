def handle_message(response, transcript_buffer):
    """Handle different types of messages from the server."""
    msg_type = response.get("type", "")
    
    # Handle text transcript deltas (chunked responses)
    if msg_type == "response.text.delta":
        # add the text delta to the buffer
        delta = response.get("delta", "")
        transcript_buffer += delta

        # Return both the buffer and the chunk
        return transcript_buffer, delta  

    # Final text transcript is received
    elif msg_type == "response.text.done":
        # get the final chunk
        final_chunk = transcript_buffer

        # Clear the buffer after final text is handled
        return "", final_chunk  

    # Handle audio transcript deltas (chunked audio responses)
    elif msg_type == "response.audio_transcript.delta":
        # add the transcript delta to the buffer
        delta = response.get("transcript", "")
        transcript_buffer += delta

        # Return both the buffer and the chunk
        return transcript_buffer, delta  

    # Handle audio transcript completion
    elif msg_type == "response.output_item.done":
        # get the item content
        content_list = response.get('item', {}).get('content', [])
        final_chunk = ""

        # loop through the content list
        for content in content_list:
            # if it's an audio transcript
            if content.get('type') == 'audio' and 'transcript' in content:
                # add the transcript to the buffer
                final_chunk += content['transcript']

        # Clear the buffer after final transcript
        return "", final_chunk  

    # Handle response completion
    elif msg_type == "response.done":
        # No chunk, just return the buffer
        return transcript_buffer, None  

    # Handle audio chunks
    elif msg_type == "response.audio.delta":
        # get the audio chunk
        audio_chunk = response.get("delta", "")

        # Return the buffer and the audio chunk
        return transcript_buffer, audio_chunk  

    # Suppress unnecessary message types
    ignored_message_types = [
        "session.created", "session.updated", "response.created", 
        "rate_limits.updated", "response.output_item.added", 
        "conversation.item.created", "response.content_part.added", 
        "response.output_item.done"
    ]
    
    # check for ignored messages
    if msg_type in ignored_message_types:
        # Ignore these message types silently
        return transcript_buffer, None  
    
    # Return buffer and None for unhandled message types
    return transcript_buffer, None
