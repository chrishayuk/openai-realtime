# connection_handler.py
import websockets

# Function to handle WebSocket connection setup
async def connect_to_server(url, headers, ssl_context):
    """Connect to the WebSocket server and return the connection object."""
    ws = None
    try:
        # Connect to WebSocket server
        ws = await websockets.connect(url, extra_headers=headers, ssl=ssl_context)
        print("Connected to server.")
        return ws
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Function to close WebSocket connection
async def close_connection(ws):
    """Close the WebSocket connection."""
    if ws is not None and not ws.closed:
        await ws.close()
        print("WebSocket connection closed.")