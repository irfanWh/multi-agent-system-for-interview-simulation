import math
import struct
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AudioBuffer:
    """
    Accumulates raw PCM chunks from browser AudioWorklet.
    Detects end-of-speech using energy-based VAD + silence timer.
    Expects 16kHz 16-bit mono PCM data.
    """
    SAMPLE_RATE = 16000
    SILENCE_THRESHOLD_MS = 1200  # Wait a bit longer before deciding user is done
    MIN_SPEECH_MS = 500
    ENERGY_THRESHOLD = 0.015  # Slightly higher to ignore background noise

    def __init__(self):
        self.buffer = bytearray()
        self.state = "IDLE"  # IDLE, SPEAKING, SILENCE
        self.speech_start_time_ms = 0
        self.silence_start_time_ms = 0
        self.current_time_ms = 0
        self._frame_count = 0

    def _compute_energy(self, pcm_bytes: bytes) -> float:
        """
        Compute RMS energy of the frame.
        Assumes 16-bit signed PCM (Int16), 2 bytes per sample.
        """
        if len(pcm_bytes) % 2 != 0:
            return 0.0
            
        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return 0.0
            
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)
        sq_sum = sum((sample / 32768.0) ** 2 for sample in samples)
        return math.sqrt(sq_sum / num_samples)

    def add_chunk(self, chunk: bytes) -> Optional[bytes]:
        """
        Add a PCM frame. Updates VAD state.
        Returns complete utterance bytes when end-of-speech detected,
        None otherwise.
        """
        self.buffer.extend(chunk)
        
        chunk_duration_ms = (len(chunk) / 2 / self.SAMPLE_RATE) * 1000
        self.current_time_ms += chunk_duration_ms

        energy = self._compute_energy(chunk)
        is_speech = energy > self.ENERGY_THRESHOLD

        self._frame_count += 1
        # Log every 50 frames (~1.6s at 128 samples/frame) to avoid spam
        if self._frame_count % 50 == 0:
            logger.debug(f"AudioBuffer: state={self.state} energy={energy:.4f} is_speech={is_speech} "
                        f"time={self.current_time_ms:.0f}ms buf={len(self.buffer)}B")

        if self.state == "IDLE":
            if is_speech:
                self.state = "SPEAKING"
                self.speech_start_time_ms = self.current_time_ms
                logger.info(f"VAD: Speech started at {self.current_time_ms:.0f}ms")
                
        elif self.state == "SPEAKING":
            if not is_speech:
                self.state = "SILENCE"
                self.silence_start_time_ms = self.current_time_ms
                
        elif self.state == "SILENCE":
            if is_speech:
                self.state = "SPEAKING"
            else:
                silence_duration = self.current_time_ms - self.silence_start_time_ms
                if silence_duration >= self.SILENCE_THRESHOLD_MS:
                    speech_duration = self.silence_start_time_ms - self.speech_start_time_ms
                    
                    if speech_duration < self.MIN_SPEECH_MS:
                        logger.info(f"VAD: Noise burst ignored ({speech_duration:.0f}ms < {self.MIN_SPEECH_MS}ms)")
                        self.reset()
                        return None
                    else:
                        logger.info(f"VAD: End-of-speech! speech={speech_duration:.0f}ms "
                                   f"silence={silence_duration:.0f}ms buf={len(self.buffer)}B")
                        utterance = bytes(self.buffer)
                        self.reset()
                        return utterance

        return None

    def reset(self):
        """Clear buffer after utterance fired."""
        self.buffer = bytearray()
        self.state = "IDLE"
        self.current_time_ms = 0
        self.speech_start_time_ms = 0
        self.silence_start_time_ms = 0
        self._frame_count = 0
