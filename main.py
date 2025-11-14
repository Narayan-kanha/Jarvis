# main.py
"""
Entry point for the modular Jarvis app.
Loads config.json, loads whisper models (asks to download if needed),
starts WakewordListener (Porcupine if present, fallback to whisper),
and creates the GUI (ui/window.JarvisGUI).
"""

import os
import json
import threading

CONFIG_PATH = "config.json"

def load_config(path=CONFIG_PATH):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # defaults
    return {
        "mic_device": None,
        "idle_model": "tiny",
        "active_model": "medium",
        "screen_model": "base",
        "wakeword_enabled": True,
        "dark_mode": True,
        "porcupine_access_key": None
    }

def save_config(cfg, path=CONFIG_PATH):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def main():
    cfg = load_config()

    # lazy import heavy modules
    from core.asr import ensure_model_with_prompt
    from core.wakeword import WakewordListener
    from ui.window import JarvisGUI

    models = {}
    try:
        print("[main] Loading idle model:", cfg.get("idle_model"))
        models["idle"] = ensure_model_with_prompt(cfg.get("idle_model", "tiny"))
        print("[main] Loading active model:", cfg.get("active_model"))
        models["active"] = ensure_model_with_prompt(cfg.get("active_model", "medium"))
        print("[main] Loading screen model:", cfg.get("screen_model"))
        models["screen"] = ensure_model_with_prompt(cfg.get("screen_model", "base"))
    except Exception as exc:
        print("[main] Model loading failed:", exc)
        # Continue: GUI can still run but functions will complain if models missing.

    wake_engine = None
    if cfg.get("wakeword_enabled", True):
        try:
            # use porcupine if present, otherwise fallback will use whisper idle model
            wake_engine = WakewordListener(
                on_wakeword=lambda: print("[main] Wakeword detected (callback placeholder)"),
                wakeword="jarvis",
                porcupine_access_key=cfg.get("porcupine_access_key"),
                use_porcupine=True,
                whisper_model=models.get("idle"),
                device=cfg.get("mic_device")
            )
            # start listener in background; GUI will receive its own listener if preferred.
            wake_engine.start()
        except Exception as exc:
            print("[main] Wakeword engine failed to start:", exc)
            wake_engine = None

    # Create GUI and hand over control
    # The GUI itself will optionally start its own idle loops if LISTEN_MODE configured there.
    app = JarvisGUI(models=models, wakeword_engine=wake_engine, config_path=CONFIG_PATH)
    # If the wakeword engine is present, attach a GUI callback for when detected:
    if wake_engine:
        def gui_wake_cb():
            try:
                app.after(0, lambda: app._wakeword_simulation() if hasattr(app, "_wakeword_simulation") else app.gui_callback(assistant_text="Wakeword detected", status="Listening"))
            except Exception:
                try:
                    app.gui_callback(assistant_text="Wakeword detected", status="Listening")
                except Exception:
                    pass
        # Ensure WakewordListener calls GUI friendly callback: override on_wakeword if possible
        try:
            wake_engine.on_wakeword = lambda: app.after(0, app._wakeword_simulation if hasattr(app, "_wakeword_simulation") else lambda: app.gui_callback(assistant_text="Wakeword detected", status="Listening"))
        except Exception:
            pass

    try:
        app.mainloop()
    finally:
        # cleanup
        try:
            if wake_engine:
                wake_engine.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
