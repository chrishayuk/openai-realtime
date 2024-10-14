import argparse

# Set the defaults
DEFAULT_VOICE = "alloy"
DEFAULT_SYSTEM_MESSAGE = ("Your knowledge cutoff is 2023-10. You are a helpful, witty, and friendly AI. "
                          "Act like a human, but remember that you aren't a human and that you can't do human things "
                          "in the real world. Your voice and personality should be warm and engaging, with a lively and "
                          "playful tone.")

def parse_arguments():
    # Setup the argument parser
    parser = argparse.ArgumentParser(description="Choose between text or audio for the session.")

    # Text or audio mode
    parser.add_argument("--mode", choices=["text", "audio"], default="text",
                        help="Select the output mode: 'text' for text-based response, 'audio' for audio response.")

    # Streaming argument
    parser.add_argument("--no-streaming", action="store_true",
                        help="Disable streaming mode. If set, final response mode will be used.")

    # Optional audio file or mic
    parser.add_argument("--audio-source", choices=["mic", "file"], default=None,
                        help="Choose the audio source: 'mic' to record from microphone or 'file' for an audio file.")

    # System prompt and voice parameters
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_MESSAGE, help="Set a custom system prompt.")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Set the voice for audio responses.")

    # Parse arguments
    return parser.parse_args()
