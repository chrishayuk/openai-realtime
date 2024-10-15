import base64
import numpy as np
import g711
import logging

# Initialize logging
logger = logging.getLogger(__name__)

def decode_audio(audio_chunk, audio_format='pcm'):
    """Decode the received audio chunk based on the format (PCM or G.711)."""
    try:
        # Step 1: Base64 decode the chunk
        decoded_audio = base64.b64decode(audio_chunk)

        # Step 2: Handle based on the audio format
        if audio_format == 'pcm':
            # Raw PCM 16-bit, little-endian, 24kHz
            audio_array = np.frombuffer(decoded_audio, dtype=np.int16)
            
            # Return raw PCM audio data for playback
            return audio_array.tobytes()
            
        elif audio_format == 'g711_ulaw':
            # Decode G.711 u-law to PCM
            decoded_pcm = g711.decode_pcm(decoded_audio)
            decoded_pcm = np.array(decoded_pcm, dtype=np.int16)  # Explicitly cast to int16

            # debug
            logger.debug(f"Decoded G.711 u-law audio to PCM, size: {len(decoded_pcm)} bytes")
            logger.debug(f"First few decoded G.711 u-law PCM samples: {decoded_pcm[:20]}")

            # Return for playback
            return decoded_pcm.tobytes()

        elif audio_format == 'g711_alaw':
            # Decode G.711 a-law to PCM
            decoded_pcm = g711.decode_alaw(decoded_audio)
            decoded_pcm = np.array(decoded_pcm, dtype=np.int16)  # Explicitly cast to int16

            # debug
            logger.debug(f"Decoded G.711 a-law audio to PCM, size: {len(decoded_pcm)} bytes")
            logger.debug(f"First few decoded PCM samples: {decoded_pcm[:20]}")

            # Return as PCM for playback
            return decoded_pcm.tobytes()  

        else:
            logger.info("Unknown audio format")
            return None
    except Exception as e:
        logger.error(f"Error decoding audio: {e}")
        return None
