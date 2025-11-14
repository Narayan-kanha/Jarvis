# core/wakeword.py
"""
WakewordListener

Two modes:
 - Porcupine mode (recommended): uses pvporcupine (Picovoice Porcupine) for reliable KWS.
 - Whisper fallback mode: runs short idle transcriptions with a Whisper model and checks for wakeword text.

API:
    listener = WakewordListener(on_wakeword=callback, wakeword='jarvis', porcupine_access_key=None, use_porcupine=True, whisper_model=whisper_idle)
    listener.start()
    listener.stop()

Callback signature:
    def callback():
        # called when wakeword detected
"""

import threading
import time
import collections
import traceback
from typing import Callable, Optional

# Guard import for pvporcupine
try:
    import pvporcupine
    PV_AVAILABLE = True
except Exception:
    pvporcupine = None
    PV_AVAILABLE = False

import sounddevice as sd
import numpy as np

class WakewordListener:
    def __init__(
        self,
        on_wakeword: Callable[[], None],
        wakeword: str = "jarvis",
        porcupine_access_key: Optional[str] = None,
        use_porcupine: bool = True,
        whisper_model = None,
        device: Optional[int] = None,
        sample_rate: int = 16000,
        frame_length: int = 512
    ):
        """
        on_wakeword: function called when wakeword detected
        wakeword: keyword to detect (for whisper fallback)
        porcupine_access_key: required by pvporcupine if using Porcupine with access_key
        use_porcupine: try pvporcupine if available (best)
        whisper_model: whisper model instance for fallback (fast model recommended)
        device: sounddevice device id (None = default)
        """
        self.on_wakeword = on_wakeword
        self.wakeword = wakeword.lower().strip()
        self.use_porcupine = use_porcupine and PV_AVAILABLE
        self.porcupine_access_key = porcupine_access_key
        self.whisper_model = whisper_model
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.device = device

        self._stop_event = threading.Event()
        self._thread = None

        # Porcupine object (if using)
        self._porcupine = None
        if self.use_porcupine and PV_AVAILABLE:
            try:
                # default keyword can be e.g. 'jarvis' if a built-in keyword exists; else user loads custom model
                kws = [self.wakeword]
                self._porcupine = pvporcupine.create(keywords=kws) if porcupine_access_key is None else pvporcupine.create(access_key=porcupine_access_key, keywords=kws)
            except Exception:
                self._porcupine = None
                # fallback to whisper mode automatically
                self.use_porcupine = False

    def start(self):
        """Start the listener in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the listener."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        # cleanup porcupine
        try:
            if self._porcupine:
                self._porcupine.delete()
        except Exception:
            pass

    def _run(self):
        if self.use_porcupine and self._porcupine:
            self._run_porcupine()
        else:
            self._run_whisper_fallback()

    # ---------- Porcupine mode ----------
    def _run_porcupine(self):
        try:
            # porcupine expects 16k 16-bit PCM mono frames of a certain frame_length (e.g. 512)
            frame_length = self._porcupine.frame_length
            sr = self.sample_rate
            stream = sd.InputStream(samplerate=sr, channels=1, dtype='int16', blocksize=frame_length, device=self.device)
            stream.start()
            while not self._stop_event.is_set():
                pcm, _ = stream.read(frame_length)
                # flatten to 1D int16 array
                pcm = np.frombuffer(pcm, dtype=np.int16)
                try:
                    keyword_index = self._porcupine.process(pcm)
                    if keyword_index >= 0:
                        # detected
                        try:
                            self.on_wakeword()
                        except Exception:
                            traceback.print_exc()
                        # small sleep to avoid immediate retrigger
                        time.sleep(0.5)
                except Exception:
                    # sometimes porcupine.process raises; ignore and continue
                    traceback.print_exc()
        except Exception as exc:
            print("WakewordListener Porcupine failed, switching to fallback. Error:", exc)
            self._run_whisper_fallback()

    # ---------- Whisper fallback mode ----------
    def _run_whisper_fallback(self):
        """
        Fallback that records short segments and uses a small whisper model to transcribe.
        This is CPU/GPU heavier and less robust than Porcupine, but it works without extra deps.
        whisper_model must be provided for this fallback.
        """
        if self.whisper_model is None:
            print("WakewordListener: No porcupine available and no whisper_model provided for fallback. Listener will not run.")
            return

        # we record short clips and transcribe using the whisper idle model
        sr = self.sample_rate
        block_sec = 2.0
        block_samples = int(sr * block_sec)
        # use a tiny rolling buffer & simple logic to avoid constant transcriptions
        silence_pause = 0.6

        try:
            while not self._stop_event.is_set():
                audio = sd.rec(block_samples, samplerate=sr, channels=1, dtype='int16', device=self.device)
                sd.wait()
                # write to a temp file and transcribe (whisper expects float32/16k but whisper.load_model handles file paths)
                import tempfile, soundfile as sf
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tf:
                    fname = tf.name
                    sf.write(fname, audio, sr)
                    try:
                        res = self.whisper_model.transcribe(fname, language='en')
                        text = res.get('text', '').lower()
                    except Exception as exc:
                        text = ''
                        print("WakewordListener fallback transcription error:", exc)
                if self.wakeword in text:
                    try:
                        self.on_wakeword()
                    except Exception:
                        traceback.print_exc()
                    # small cooldown
                    time.sleep(0.6)
                else:
                    # small pause
                    time.sleep(silence_pause)
        except Exception as exc:
            print("WakewordListener fallback loop died:", exc)

# Example usage (not executed on import)
if __name__ == "__main__":
    def on_wake():
        print("WAKEWORD DETECTED")

    wl = WakewordListener(on_wake, wakeword='jarvis', use_porcupine=False, whisper_model=None)
    print("Starting listener (example)")
    wl.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        wl.stop()
        print("Stopped")
