# core/wakeword.py
"""
WakewordListener:
 - Uses Porcupine (pvporcupine) if available (recommended)
 - Falls back to short Whisper transcriptions if Porcupine missing
API:
  wl = WakewordListener(on_wakeword=cb, wakeword='jarvis', porcupine_access_key=None, use_porcupine=True, whisper_model=whisper_idle)
  wl.start(); wl.stop()
"""

import threading
import time
import traceback

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
        on_wakeword,
        wakeword="jarvis",
        porcupine_access_key=None,
        use_porcupine=True,
        whisper_model=None,
        device=None,
        sample_rate: int = 16000,
    ):
        self.on_wakeword = on_wakeword
        self.wakeword = wakeword.lower().strip()
        self.use_porcupine = use_porcupine and PV_AVAILABLE
        self.porcupine_access_key = porcupine_access_key
        self.whisper_model = whisper_model
        self.sample_rate = sample_rate
        self.device = device

        self._stop_event = threading.Event()
        self._thread = None
        self._porcupine = None

        if self.use_porcupine and PV_AVAILABLE:
            try:
                # NOTE: Porcupine's built-in keywords are limited (e.g., 'jarvis' may work if installed).
                # If a custom keyword file is required, user must provide it.
                kws = [self.wakeword]
                if porcupine_access_key:
                    self._porcupine = pvporcupine.create(access_key=porcupine_access_key, keywords=kws)
                else:
                    self._porcupine = pvporcupine.create(keywords=kws)
            except Exception as exc:
                print("[wakeword] Porcupine init failed:", exc)
                self._porcupine = None
                self.use_porcupine = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
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

    def _run_porcupine(self):
        try:
            frame_length = self._porcupine.frame_length
            sr = self.sample_rate
            stream = sd.InputStream(samplerate=sr, channels=1, dtype="int16", blocksize=frame_length, device=self.device)
            stream.start()
            while not self._stop_event.is_set():
                pcm, _ = stream.read(frame_length)
                # flatten to 1D int16 array
                try:
                    pcm_flat = pcm.flatten().astype(np.int16)
                except Exception:
                    pcm_flat = np.frombuffer(pcm, dtype=np.int16)
                try:
                    idx = self._porcupine.process(pcm_flat)
                    if idx >= 0:
                        try:
                            self.on_wakeword()
                        except Exception:
                            traceback.print_exc()
                        time.sleep(0.5)
                except Exception:
                    traceback.print_exc()
        except Exception as exc:
            print("[wakeword] Porcupine mode failed, falling back:", exc)
            self._run_whisper_fallback()

    def _run_whisper_fallback(self):
        """
        Simple fallback: record short segments and transcribe via a small whisper model.
        whisper_model must be provided for this fallback.
        """
        if self.whisper_model is None:
            print("[wakeword] No whisper model for fallback; listener not running.")
            return

        sr = self.sample_rate
        block_sec = 1.6
        block_samples = int(sr * block_sec)
        try:
            import soundfile as sf
            import tempfile
            while not self._stop_event.is_set():
                audio = sd.rec(block_samples, samplerate=sr, channels=1, dtype="int16", device=self.device)
                sd.wait()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tf:
                    sf.write(tf.name, audio, sr)
                    try:
                        res = self.whisper_model.transcribe(tf.name, language="en")
                        text = res.get("text", "").lower()
                    except Exception as exc:
                        print("[wakeword] fallback transcribe error:", exc)
                        text = ""
                if self.wakeword in text:
                    try:
                        self.on_wakeword()
                    except Exception:
                        traceback.print_exc()
                    time.sleep(0.6)
                else:
                    time.sleep(0.4)
        except Exception as exc:
            print("[wakeword] fallback loop died:", exc)
