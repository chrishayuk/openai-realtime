import asyncio
import os
import ssl
import argparse
import json
import sys
from dotenv import load_dotenv
from session import send_session_update  # Import session update from session.py
from message_handler import handle_message  # Import message handler
from connection_handler import connect_to_server, close_connection  # Import connection handling

# Constants for session update
VOICE = "alloy"
SYSTEM_MESSAGE = "Please assist the user with information."

# SSL context to disable certificate verification
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Load environment variables from .env file
load_dotenv()

# WebSocket URL
url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

# Retrieve OpenAI API Key from environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {api_key}",
    "OpenAI-Beta": "realtime=v1"
}

# Function to handle sending messages interactively
async def send_message(ws, modalities):
    """Send user messages interactively."""
    try:
        while True:
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "You: ")  # Async input handling
            if not user_input.strip():
                continue  # Ignore empty input

            # Send user message to the server
            await ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": modalities,
                    "instructions": user_input
                }
            }))
    except KeyboardInterrupt:
        print("\nExiting chat...")

# Function to receive and handle messages from the WebSocket
async def receive_messages(ws):
    """Receive messages from the server and handle them."""
    transcript_buffer = ""  # Initialize the buffer locally
    try:
        async for message in ws:
            response = json.loads(message)
            # Handle the response and extract transcript or audio chunks
            transcript_buffer = handle_message(response, transcript_buffer)
    except asyncio.CancelledError:
        print("\nMessage receiving task canceled.")
    except websockets.ConnectionClosed as e:
        print(f"\nConnection closed by server: {e}")
    except Exception as e:
        print(f"An error occurred while receiving: {e}")

# Main function to run the interactive chat CLI
async def main(modalities):
    # Connect to the server
    ws = await connect_to_server(url, headers, ssl_context)
    if ws is None:
        print("Failed to connect to server.")
        return

    try:
        # Send the session update with selected modalities
        await send_session_update(ws, modalities, VOICE, SYSTEM_MESSAGE)

        print("Start chatting! (Press Ctrl+C to exit)\n")

        # Create tasks to handle sending and receiving simultaneously
        receive_task = asyncio.create_task(receive_messages(ws))
        send_task = asyncio.create_task(send_message(ws, modalities))

        # Ensure both tasks run concurrently
        await asyncio.gather(receive_task, send_task)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close WebSocket connection
        await close_connection(ws)
        receive_task.cancel()  # Ensure the receiving task is canceled

# Entry point with CLI argument parsing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Choose between text or audio for the session.")
    parser.add_argument("--mode", choices=["text", "audio"], default="text",
                        help="Select the output mode: 'text' for text-based response, 'audio' for audio response.")

    args = parser.parse_args()

    # Set modalities based on CLI input
    if args.mode == "audio":
        modalities = ["text", "audio"]
    else:
        modalities = ["text"]

    try:
        asyncio.run(main(modalities))
    except KeyboardInterrupt:
        print("\nDisconnected from server by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
