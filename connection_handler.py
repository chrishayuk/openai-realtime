# connection_handler.py
from dotenv import load_dotenv
import os
import ssl
import sys
import websockets

# Load environment variables from .env file
load_dotenv()

# WebSocket URL
URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

# Retrieve OpenAI API Key from environment
API_KEY = os.getenv("OPENAI_API_KEY")

# get the api key
if not API_KEY:
    print("Error: OPENAI_API_KEY environment variable not set.")
    sys.exit(1)

# set the headers
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "OpenAI-Beta": "realtime=v1"
}

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Function to handle WebSocket connection setup
async def connect_to_server():
    """Connect to the WebSocket server and return the connection object."""
    ws = None
    try:
        # Connect to WebSocket server
        ws = await websockets.connect(URL, extra_headers=HEADERS, ssl=ssl_context)

        # connected
        print("Connected to server.")

        # return the socket
        return ws
    except websockets.exceptions.ConnectionClosed as e:
        # connection closed
        print(f"Connection closed: {e}")

        # no socket
        return None
    except Exception as e:
        # error
        print(f"Error: {e}")

        # no socket
        return None

# Function to close WebSocket connection
async def close_connection(ws):
    """Close the WebSocket connection."""
    if ws is not None and not ws.closed:
        await ws.close()
        print("WebSocket connection closed.")