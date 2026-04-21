import time
from typing import Optional

class AudioBuffer:
    def __init__(self):
        self.buffer = bytearray()
        self.last_speech_time = time.time()
        self.has_speech = False
        
    def add_chunk(self, chunk: bytes, is_silence: bool):
        """Accumulate chunks and track silence timing."""
        self.buffer.extend(chunk)
        
        if not is_silence:
            self.last_speech_time = time.time()
            self.has_speech = True

    def get_complete_utterance(self) -> Optional[bytes]:
        """
        Return buffer if silence > 500ms is detected after speech was detected.
        """
        if not self.has_speech:
            return None
            
        silence_duration = time.time() - self.last_speech_time
        if silence_duration > 0.5:
            return bytes(self.buffer)
            
        return None

    def reset(self):
        """Clear the buffer for the next utterance."""
        self.buffer = bytearray()
        self.last_speech_time = time.time()
        self.has_speech = False
