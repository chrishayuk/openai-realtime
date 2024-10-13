import pyaudio
import numpy as np

def play_audio(audio_data):
    """Play back raw PCM audio data using pyaudio with proper format settings."""
    SAMPLE_RATE = 24000  # Hz
    CHANNELS = 1  # Mono
    FORMAT = pyaudio.paInt16  # 16-bit PCM audio

    p = None  # Initialize pyaudio instance variable
    stream = None  # Initialize stream variable

    try:
        # Convert the byte data into numpy array (16-bit PCM)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Initialize pyaudio
        p = pyaudio.PyAudio()

        # Open a stream to play audio at 24kHz sample rate
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE, output=True)

        # Play the audio
        stream.write(audio_array.tobytes())

    except Exception as e:
        print(f"Error playing audio: {e}")

    finally:
        # Ensure that stream and pyaudio instances are properly closed
        if stream is not None:
            stream.stop_stream()
            stream.close()

        if p is not None:
            p.terminate()
