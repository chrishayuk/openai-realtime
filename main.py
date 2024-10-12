# main.py
import asyncio
import argparse
import json
import websockets
from session import send_session_update  # Import session update from session.py
from message_handler import handle_message  # Import message handler
from connection_handler import connect_to_server, close_connection  # Import connection handling

# Constants for session update
VOICE = "alloy"
SYSTEM_MESSAGE = "Please assist the user with information."

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
    except websockets.ConnectionClosed as e:
        # handle disconnections
        if e.code == 1000:  # Normal closure
            print("Connection closed by the server (normal).")

        else:  # Unexpected disconnection
            print(f"Connection closed unexpectedly with code {e.code}: {e.reason}")
    except asyncio.CancelledError:
        # cancelling
        print("\nMessage receiving task canceled.")
    except Exception as e:
        # error receiving
        print(f"An error occurred while receiving: {e}")


# Main function to run the interactive chat CLI
async def main(modalities):
    # Connect to the server
    ws = await connect_to_server()

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
        # error
        print(f"An error occurred: {e}")

    finally:
        # Ensure tasks are canceled gracefully
        receive_task.cancel()
        send_task.cancel()

        # wait until they're done
        await asyncio.gather(receive_task, send_task, return_exceptions=True)
        
        # Close WebSocket connection
        await close_connection(ws)


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
