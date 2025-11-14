# main.py
"""
Entry point for modular Jarvis.

- Loads config.json and credentials.json (credentials.json holds porcupine access key and keyword path)
- Loads whisper models via core.asr.ensure_model_with_prompt()
- Starts GUI and WakewordListener (Porcupine if available)
"""

import os
import json
import threading
import time
import sys

from core.asr import ensure_model_with_prompt
from core.wakeword import WakewordListener

# UI import (delayed to avoid heavy imports before models loaded)
def import_gui():
    from ui.window import JarvisGUI
    return JarvisGUI

# config paths
CONFIG_PATH = "config.json"
CREDENTIALS_PATH = "credentials.json"

DEFAULT_CONFIG = {
    "idle_model": "tiny",
    "active_model": "medium",
    "screen_model": "base",
    "wakeword_enabled": True,
    "dark_mode": True,
    "listen_mode": "both",
}

def load_json_or_default(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # fill defaults
                for k, v in default.items():
                    data.setdefault(k, v)
                return data
        except Exception as e:
            print(f"[main] Failed to read {path}: {e}")
            return dict(default)
    else:
        return dict(default)

def main():
    # load config + credentials
    cfg = load_json_or_default(CONFIG_PATH, DEFAULT_CONFIG)
    creds = load_json_or_default(CREDENTIALS_PATH, {})

    idle_model_name = cfg.get("idle_model", "tiny")
    active_model_name = cfg.get("active_model", "medium")
    screen_model_name = cfg.get("screen_model", "base")

    # Load whisper models (these may prompt to download via core/asr)
    print(f"[main] Loading idle model: {idle_model_name}")
    whisper_idle = ensure_model_with_prompt(idle_model_name)

    print(f"[main] Loading active model: {active_model_name}")
    whisper_active = ensure_model_with_prompt(active_model_name)

    print(f"[main] Loading screen model: {screen_model_name}")
    whisper_screen = ensure_model_with_prompt(screen_model_name)

    models = {
        "idle": whisper_idle,
        "active": whisper_active,
        "screen": whisper_screen
    }

    # import GUI class now
    JarvisGUI = import_gui()

    # instantiate GUI (this creates the window but does not start mainloop yet)
    gui = JarvisGUI(models=models, wakeword_engine=None)

    # Build wakeword listener using credentials
    porcupine_key = creds.get("porcupine_access_key") or None
    porcupine_kw_path = creds.get("porcupine_keyword_path") or None
    use_porcupine = bool(creds.get("porcupine_keyword_path") or porcupine_key)

    wake_listener = None
    if cfg.get("wakeword_enabled", True):
        try:
            # Attach GUI method as callback — gui class has _wakeword_triggered method (keeps GUI threading safe via .after)
            on_wake = getattr(gui, "_wakeword_triggered", None)
            if on_wake is None:
                # fallback: call gui.gui_callback to show message
                def on_wake():
                    gui.gui_callback(assistant_text="Wakeword detected", status="Wakeword")
            else:
                on_wake = on_wake

            wake_listener = WakewordListener(
                on_wakeword=on_wake,
                wakeword="jarvis",
                porcupine_access_key=porcupine_key,
                porcupine_keyword_path=porcupine_kw_path,
                use_porcupine=use_porcupine,
                whisper_model=whisper_idle,
                device=None
            )
            wake_listener.start()
            print("[main] Wakeword listener started (Porcupine if available).")
        except Exception as e:
            print("[main] Failed to start WakewordListener:", e)

    # store listener on gui so it can be stopped if GUI quits
    try:
        gui.wake_listener = wake_listener
    except Exception:
        pass

    # Start GUI loop
    try:
        gui.mainloop()
    finally:
        # ensure listener is stopped when exiting
        try:
            if wake_listener:
                wake_listener.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
