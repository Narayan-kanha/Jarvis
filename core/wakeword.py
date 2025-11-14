# core/wakeword.py
"""
Robust WakewordListener.

- Uses pvporcupine (Porcupine) if available.
  - Accepts either a built-in keyword name (e.g. "jarvis") OR a custom keyword file (.ppn)
  - Accepts an access_key (if your pvporcupine requires it)
  - Tries several pvporcupine.create() signatures to handle different installs/versions.

- Falls back to a simple Whisper-based recorder/transcribe loop if Porcupine not available or fails.

API:
    wl = WakewordListener(on_wakeword=callback, wakeword="jarvis",
                          porcupine_access_key="...", porcupine_keyword_path="path/to/hey-jarvis.ppn",
                          use_porcupine=True, whisper_model=whisper_idle, device=None)
    wl.start()
    wl.stop()
"""

import threading
import time
import traceback
from typing import Callable, Optional
import os

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
        porcupine_keyword_path: Optional[str] = None,
        use_porcupine: bool = True,
        whisper_model=None,
        device: Optional[int] = None,
        sample_rate: int = 16000,
    ):
        """
        on_wakeword: function called when wakeword detected (should be thread-safe)
        wakeword: fallback built-in keyword name (e.g., 'jarvis')
        porcupine_access_key: (optional) Picovoice access key required by some pvporcupine versions
        porcupine_keyword_path: (optional) path to a .ppn custom keyword file
        use_porcupine: attempt Porcupine if PV_AVAILABLE
        whisper_model: whisper model instance (for fallback)
        device: sounddevice device id (or None)
        """
        self.on_wakeword = on_wakeword
        self.wakeword = (wakeword or "jarvis").lower().strip()
        self.porcupine_access_key = porcupine_access_key or None
        self.porcupine_keyword_path = porcupine_keyword_path or None
        self.use_porcupine = bool(use_porcupine) and PV_AVAILABLE
        self.whisper_model = whisper_model
        self.device = device
        self.sample_rate = int(sample_rate)

        self._stop_event = threading.Event()
        self._thread = None
        self._porcupine = None

        # prepare porcupine if requested
        if self.use_porcupine and PV_AVAILABLE:
            try:
                self._init_porcupine()
            except Exception as exc:
                print("[wakeword] Porcupine init failed:", exc)
                self._porcupine = None
                self.use_porcupine = False

    def _init_porcupine(self):
        """
        Try to construct a pvporcupine.Porcupine object with a few possible signatures:
         - pvporcupine.create(access_key=..., keyword_paths=[...])
         - pvporcupine.create(access_key=..., keywords=[...])
         - pvporcupine.create(keyword_paths=[...])
         - pvporcupine.create(keywords=[...])
        Also supports passing a single keyword path (string).
        """
        kws = None
        kpaths = None

        if self.porcupine_keyword_path and os.path.exists(self.porcupine_keyword_path):
            kpaths = [self.porcupine_keyword_path]
        else:
            kws = [self.wakeword]

        # Try multiple signatures — some pvporcupine builds require the access_key param, some don't.
        last_exc = None
        attempts = []
        # preferred: pass access_key when provided
        if self.porcupine_access_key:
            if kpaths:
                attempts.append(lambda: pvporcupine.create(access_key=self.porcupine_access_key, keyword_paths=kpaths))
            if kws:
                attempts.append(lambda: pvporcupine.create(access_key=self.porcupine_access_key, keywords=kws))
        # fallback signatures (older/newer variants)
        if kpaths:
            attempts.append(lambda: pvporcupine.create(keyword_paths=kpaths))
        if kws:
            attempts.append(lambda: pvporcupine.create(keywords=kws))

        for fn in attempts:
            try:
                self._porcupine = fn()
                # success
                return
            except TypeError as e:
                # signature mismatch; try next
                last_exc = e
            except Exception as e:
                last_exc = e

        # if we exit here, none worked
        raise RuntimeError(f"pvporcupine.create failed (last error: {last_exc})")

    def start(self):
        """Start background thread to listen for wakeword."""
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
        # clean up porcupine
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
            frame_length = getattr(self._porcupine, "frame_length", None) or 512
            sr = self.sample_rate
            stream = sd.InputStream(samplerate=sr, channels=1, dtype="int16", blocksize=frame_length, device=self.device)
            stream.start()
            while not self._stop_event.is_set():
                pcm, _ = stream.read(frame_length)
                # ensure flattened int16 array
                try:
                    arr = np.frombuffer(pcm, dtype=np.int16)
                except Exception:
                    arr = np.array(pcm).astype(np.int16).flatten()
                try:
                    idx = self._porcupine.process(arr)
                    if idx >= 0:
                        # detected
                        try:
                            self.on_wakeword()
                        except Exception:
                            traceback.print_exc()
                        # short cooldown
                        time.sleep(0.5)
                except Exception:
                    # if porcupine occasionally errors, ignore and continue
                    traceback.print_exc()
        except Exception as exc:
            print("[wakeword] Porcupine loop failed, switching to fallback. Error:", exc)
            self._run_whisper_fallback()

    # ---------- Whisper fallback mode ----------
    def _run_whisper_fallback(self):
        """
        Simple fallback: record short chunks and use supplied whisper_model to transcribe.
        whisper_model should be a loaded whisper model instance.
        """
        if self.whisper_model is None:
            print("[wakeword] No porcupine and no whisper_model provided — listener will not run.")
            return

        sr = self.sample_rate
        block_sec = 2.0
        block_samples = int(sr * block_sec)

        try:
            while not self._stop_event.is_set():
                audio = sd.rec(block_samples, samplerate=sr, channels=1, dtype="int16", device=self.device)
                sd.wait()
                import tempfile, soundfile as sf
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tf:
                    fname = tf.name
                    sf.write(fname, audio, sr)
                    try:
                        res = self.whisper_model.transcribe(fname, language="en")
                        text = res.get("text", "").lower()
                    except Exception as e:
                        text = ""
                        print("[wakeword fallback] transcription error:", e)
                if self.wakeword in text:
                    try:
                        self.on_wakeword()
                    except Exception:
                        traceback.print_exc()
                    time.sleep(0.6)
                else:
                    time.sleep(0.5)
        except Exception as exc:
            print("[wakeword] fallback loop died:", exc)
