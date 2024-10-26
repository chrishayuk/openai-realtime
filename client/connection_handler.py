# connection_handler.py
import asyncio
import os
import ssl
import sys
import websockets
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# set the logger
logger = logging.getLogger(__name__)

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
    
async def connect_to_server(retry_count=3, retry_delay=5):
    """Connect to the WebSocket server and return the connection object."""
    ws = None

    # make multiple retry attemps
    for attempt in range(retry_count):
        try:
            # await the connection
            ws = await websockets.connect(URL, extra_headers=HEADERS, ssl=ssl_context)

            logger.debug("Connected to server.")
            return ws
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"Connection closed during attempt {attempt + 1}: {e}")
        except Exception as e:
            logger.error(f"Error during connection attempt {attempt + 1}: {e}")

        # Wait before retrying
        await asyncio.sleep(retry_delay)

    print(f"Failed to connect after {retry_count} attempts.")
    return None


# Function to close WebSocket connection
async def close_connection(ws):
    """Close the WebSocket connection."""
    if ws is not None and not ws.closed:
        await ws.close()
        print("WebSocket connection closed.")