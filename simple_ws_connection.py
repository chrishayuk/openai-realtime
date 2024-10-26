import asyncio
import os
import websockets
import ssl
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# WebSocket URL
URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

# Retrieve OpenAI API Key from environment
API_KEY = os.getenv("OPENAI_API_KEY")

# Headers for authorization
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "OpenAI-Beta": "realtime=v1"
}

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def test_connection():
    """Connect to the WebSocket server, send a message, and print the response."""
    try:
        # Establish connection
        async with websockets.connect(URL, extra_headers=HEADERS, ssl=ssl_context) as ws:
            print("Connected to the server!")

            # Send a simple message
            await ws.send("Hello, server!")
            
            # Wait and print the response
            response = await ws.recv()
            print(f"Server response: {response}")

    except Exception as e:
        print(f"Connection error: {e}")

# Run the test
asyncio.run(test_connection())
