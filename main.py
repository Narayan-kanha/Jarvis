# main.py
import os
import threading
import tkinter as tk
from ui.window import JarvisGUI
from core.asr import load_models, ensure_model_with_prompt
from core.wakeword import PorcupineWakeWord

# CONFIG
WHISPER_IDLE_MODEL = "tiny"
WHISPER_ACTIVE_MODEL = "medium"
WHISPER_SCREEN_MODEL = "base"
PICOVOICE_ACCESS_KEY = None  # set your Picovoice access key if using Porcupine

def main():
    # Ensure models (this will prompt the user to download if missing)
    print("[main] Loading ASR models (this may prompt to download)...")
    whisper_idle = ensure_model_with_prompt(WHISPER_IDLE_MODEL)
    whisper_active = ensure_model_with_prompt(WHISPER_ACTIVE_MODEL)
    whisper_screen = ensure_model_with_prompt(WHISPER_SCREEN_MODEL)
    models = {
        "idle": whisper_idle,
        "active": whisper_active,
        "screen": whisper_screen
    }
    print("[main] Models ready")

    # Optionally start porcupine wakeword in a separate thread and give callback to GUI.
    wake = None
    if PICOVOICE_ACCESS_KEY:
        # We'll create a placeholder callback that the GUI will replace on init
        wake = PorcupineWakeWord(access_key=PICOVOICE_ACCESS_KEY, on_detect=lambda: print("Wakeword!"))

    # Start GUI (pass models and optional wakeword handler)
    app = JarvisGUI(models=models, wakeword_engine=wake)
    app.mainloop()

if __name__ == "__main__":
    main()
