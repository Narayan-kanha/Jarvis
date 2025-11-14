# core/recorder.py
"""
Audio recording helpers used by the app.
- record_seconds_to_wav(seconds, filename, amplify=1.0)
- record_until_silence(outfile, max_duration=20, chunk_ms=300, rms_threshold=0.012, silence_chunks=3)
"""

import time
import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000
CHANNELS = 1


def record_seconds_to_wav(seconds: float, filename: str, amplify: float = 1.0) -> str:
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16")
    sd.wait()
    if amplify != 1.0:
        frames = (frames.astype("float32") * amplify).clip(-32768, 32767).astype("int16")
    sf.write(filename, frames, SAMPLE_RATE)
    return filename


def record_until_silence(outfile: str, max_duration: int = 20,
                         chunk_ms: int = 300, rms_threshold: float = 0.012, silence_chunks: int = 3) -> str:
    """
    Record until silence is detected for `silence_chunks` consecutive chunks, or max_duration reached.
    Returns WAV filename.
    """
    sr = SAMPLE_RATE
    chunk = int(chunk_ms / 1000 * sr)
    stream = sd.InputStream(samplerate=sr, channels=CHANNELS, dtype="int16", blocksize=chunk)
    stream.start()

    buffer_blocks = []
    voiced = False
    silence_count = 0
    start_time = time.time()

    try:
        while True:
            block, _ = stream.read(chunk)
            b = np.copy(block)
            buffer_blocks.append(b)

            # RMS
            rms = np.sqrt(np.mean((b.astype("float32") / 32768.0) ** 2))

            if not voiced:
                if rms > rms_threshold:
                    voiced = True
            else:
                if rms < rms_threshold:
                    silence_count += 1
                    if silence_count >= silence_chunks:
                        break
                else:
                    silence_count = 0

            if time.time() - start_time > max_duration:
                break
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

    arr = np.concatenate(buffer_blocks, axis=0)
    sf.write(outfile, arr, SAMPLE_RATE)
    return outfile
