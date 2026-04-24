import os
import logging
import httpx
from typing import AsyncIterator
import urllib.parse
import uuid

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.tts_url = os.environ.get("TTS_URL", "http://tts:5002")

    async def synthesize(self, text: str, language: str = "en") -> AsyncIterator[bytes]:
        """
        Stream WAV chunks from Coqui TTS server.
        """
        # Encode params
        params = {
            "text": text,
            "language_id": language,
            "speaker_id": "male-en-2"
        }
        
        # your_tts from Coqui uses GET /api/tts for standard server
        url = f"{self.tts_url}/api/tts?{urllib.parse.urlencode(params)}"
        
        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes(chunk_size=4096):
                            yield chunk
                return # Success, exit retry loop
            except (httpx.ConnectError, httpx.HTTPStatusError) as e:
                if attempt == max_retries - 1:
                    logger.error(f"TTS synthesis failed after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"TTS synthesis error (cold start?), retrying in {base_delay}s... ({e})")
                import asyncio
                await asyncio.sleep(base_delay)
                base_delay *= 2 # exponential backoff

    async def synthesize_to_file(self, text: str, output_dir: str = "/tmp/interviewai") -> str:
        """
        Synthesize completely and save to a WAV file.
        """
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}.wav"
        filepath = os.path.join(output_dir, filename)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                params = {
                    "text": text,
                    "language_id": "en",
                    "speaker_id": "male-en-2"
                }
                url = f"{self.tts_url}/api/tts?{urllib.parse.urlencode(params)}"
                
                response = await client.get(url)
                response.raise_for_status()
                
                with open(filepath, "wb") as f:
                    f.write(response.content)
                    
            return filepath
        except Exception as e:
            logger.error(f"TTS synthesize_to_file error: {e}")
            raise
