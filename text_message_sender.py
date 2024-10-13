import json
import uuid

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
