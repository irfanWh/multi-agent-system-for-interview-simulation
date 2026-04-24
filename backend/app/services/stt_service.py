import os
import io
import wave
import logging
import httpx
import struct

logger = logging.getLogger(__name__)

WHISPER_URL = os.environ.get("WHISPER_URL", "http://whisper:8000")

class WhisperService:
    def __init__(self):
        pass

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
        """Wrap raw 16-bit PCM bytes in a proper WAV header."""
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    async def transcribe(self, audio_bytes: bytes, language="en") -> str:
        """
        Transcribe raw 16-bit PCM audio bytes using Whisper.
        Wraps PCM in a WAV container first since Whisper expects a proper audio file.
        """
        url = f"{WHISPER_URL}/v1/audio/transcriptions"
        
        # Convert raw PCM to WAV
        wav_bytes = self._pcm_to_wav(audio_bytes)
        logger.info(f"Sending {len(wav_bytes)} bytes WAV to Whisper (PCM was {len(audio_bytes)} bytes)")
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                files = {'file': ('audio.wav', wav_bytes, 'audio/wav')}
                # Use exact model name already loaded in Whisper container
                data = {'model': 'Systran/faster-whisper-tiny', 'language': language}
                
                resp = await client.post(url, data=data, files=files)
                if resp.status_code == 200:
                    result = resp.json()
                    text = result.get("text", "")
                    logger.info(f"Whisper transcription: '{text}'")
                    return text
                else:
                    logger.error(f"Whisper transcription failed ({resp.status_code}): {resp.text}")
                    return ""
        except httpx.TimeoutException:
            logger.error("Whisper transcription timeout (>300s)")
            return ""
        except Exception as e:
            logger.error(f"Whisper exception: {str(e)}")
            return ""

    async def warmup(self):
        """Send a tiny silent audio clip to force Whisper to load the model into memory."""
        import math
        # Create a tiny 0.1s silent WAV
        pcm = struct.pack('<' + 'h'*1600, *([0]*1600))
        await self.transcribe(pcm, language="en")
