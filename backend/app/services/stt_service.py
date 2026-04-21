import os
import logging
import httpx
import struct

logger = logging.getLogger(__name__)

WHISPER_URL = os.environ.get("WHISPER_URL", "http://whisper:8000")

class WhisperService:
    def __init__(self):
        pass

    async def transcribe(self, audio_bytes: bytes, language="fr") -> str:
        url = f"{WHISPER_URL}/v1/audio/transcriptions"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                files = {'file': ('audio.webm', audio_bytes, 'audio/webm')}
                data = {'model': 'large-v3', 'language': language}
                
                resp = await client.post(url, data=data, files=files)
                if resp.status_code == 200:
                    result = resp.json()
                    return result.get("text", "")
                else:
                    logger.error(f"Whisper transcription failed: {resp.text}")
                    return ""
        except httpx.TimeoutException:
            logger.error("Whisper transcription timeout (>10s)")
            return ""
        except Exception as e:
            logger.error(f"Whisper exception: {str(e)}")
            return ""

    def detect_silence(self, audio_bytes: bytes) -> bool:
        """
        Since WebM chunks are compressed, standard VAD fails without decoding.
        For simplistic chunked WebM VAD, we assume chunks smaller than an average 
        threshold contain mostly trailing silence or very little data.
        """
        # If the WebM chunk over 250ms is very small (e.g. < 500 bytes), it is largely silence.
        return len(audio_bytes) < 500
