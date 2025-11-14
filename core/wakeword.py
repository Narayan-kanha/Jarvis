# core/wakeword.py
import threading
import time
import numpy as np

try:
    import pvporcupine
    PICO_AVAILABLE = True
except Exception:
    pvporcupine = None
    PICO_AVAILABLE = False

try:
    import sounddevice as sd
except Exception:
    sd = None

class PorcupineWakeWord:
    """
    Simple wrapper for Picovoice Porcupine.
    on_detect: callable invoked when wakeword is detected.
    """

    def __init__(self, access_key: str, on_detect, keyword: str = "jarvis"):
        if not PICO_AVAILABLE:
            raise ImportError("pvporcupine not installed. Install pvporcupine to use PorcupineWakeWord.")
        if sd is None:
            raise ImportError("sounddevice is required for PorcupineWakeWord.")
        self.access_key = access_key
        self.on_detect = on_detect
        self.keyword = keyword
        self.porcupine = pvporcupine.create(access_key=self.access_key, keywords=[keyword])
        self.frame_length = self.porcupine.frame_length
        self.sample_rate = self.porcupine.sample_rate
        self._stop = threading.Event()
        self._thread = None

    def _loop(self):
        stream = sd.InputStream(channels=1, samplerate=self.sample_rate, dtype="int16",
                                blocksize=self.frame_length)
        stream.start()
        while not self._stop.is_set():
            pcm, _ = stream.read(self.frame_length)
            pcm = np.frombuffer(pcm, dtype=np.int16)
            res = self.porcupine.process(pcm)
            if res >= 0:
                try:
                    self.on_detect()
                except Exception:
                    pass
                # short cooldown to avoid multiple triggers
                time.sleep(0.8)
        stream.stop()
        stream.close()

    def start(self):
        if self._thread:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._thread:
            return
        self._stop.set()
        self._thread.join(timeout=1)
        self._thread = None
