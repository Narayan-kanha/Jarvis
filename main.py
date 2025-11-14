# main.py
"""
Entry point for modular Jarvis.
This file instantiates the main window and (optionally) starts the wakeword listener.
Adjusted to match your project layout.
"""

import os
import json
import threading
import customtkinter as ctk

from ui.orb import AnimatedOrb
from ui.settings_window import SettingsWindow
from core.wakeword import WakewordListener

CONFIG_PATH = "./config.json"


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "mic_device": None,
        "idle_model": "tiny",
        "active_model": "medium",
        "screen_model": "base",
        "wakeword_enabled": True,
        "dark_mode": True,
    }


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)


class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config_data = load_config()
        ctk.set_appearance_mode("dark" if self.config_data.get("dark_mode", True) else "light")
        ctk.set_default_color_theme("blue")

        self.title("Jarvis")
        self.geometry("500x420")
        self.resizable(False, False)

        # orb holder frame
        orb_holder = ctk.CTkFrame(self, width=160, height=160, corner_radius=80)
        orb_holder.pack(pady=20)

        # create AnimatedOrb — IMPORTANT: use positional args (parent, gif_path, size)
        orb_gif = os.path.abspath(os.path.join("assets", "ui", "orb.gif"))
        if os.path.exists(orb_gif):
            # Correct call (positional): parent, gif_path, size
            self.orb = AnimatedOrb(orb_holder, orb_gif, 150)
        else:
            # fallback to a simple CTkLabel inside orb_holder
            lbl = ctk.CTkLabel(orb_holder, text="●", font=ctk.CTkFont(size=48, weight="bold"), text_color="#00d0ff")
            lbl.pack(expand=True)

        # controls
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10)

        self.ptt_btn = ctk.CTkButton(btn_frame, text="🎤 Push to Talk", command=self._simulate_manual_trigger)
        self.ptt_btn.grid(row=0, column=0, padx=10)

        self.settings_btn = ctk.CTkButton(btn_frame, text="⚙ Settings", command=self.open_settings)
        self.settings_btn.grid(row=0, column=1, padx=10)

        self.status_label = ctk.CTkLabel(self, text="Idle")
        self.status_label.pack(pady=20)

        # wakeword
        self.wake_listener = None
        if self.config_data.get("wakeword_enabled", True):
            self.start_wakeword_listener()

    def start_wakeword_listener(self):
        if self.wake_listener:
            self.wake_listener.stop()
        # pass in a callback — the WakewordListener implementation will call it on detection
        self.wake_listener = WakewordListener(
            on_wakeword=self.on_wakeword_detected,
            wakeword="jarvis",
            use_porcupine=True,
            whisper_model=None,
            device=self.config_data.get("mic_device")
        )
        self.wake_listener.start()
        self.status_label.configure(text="Wakeword listening...")

    def on_wakeword_detected(self):
        # marshal back to GUI thread
        self.after(0, self._wakeword_triggered)

    def _wakeword_triggered(self):
        self.status_label.configure(text="Wakeword detected!")
        try:
            self.orb.set_state("listening")
        except Exception:
            pass

        # quick simulated flow to demonstrate orb states
        self.after(1200, lambda: (self.orb.set_state("thinking"), self.status_label.configure(text="Thinking...")))
        self.after(2500, lambda: (self.orb.set_state("speaking"), self.status_label.configure(text="Speaking...")))
        self.after(3600, lambda: (self.orb.set_state("idle"), self.status_label.configure(text="Idle")))

    def _simulate_manual_trigger(self):
        self.status_label.configure(text="Manual activation!")
        try:
            self.orb.set_state("listening")
        except Exception:
            pass
        self.after(1200, lambda: (self.orb.set_state("thinking"), self.status_label.configure(text="Thinking...")))
        self.after(2400, lambda: (self.orb.set_state("speaking"), self.status_label.configure(text="Done.")))
        self.after(3600, lambda: (self.orb.set_state("idle"), self.status_label.configure(text="Idle")))

    def open_settings(self):
        SettingsWindow(self, CONFIG_PATH, on_save=self.apply_config).show()

    def apply_config(self, cfg):
        save_config(cfg)
        self.config_data = cfg
        ctk.set_appearance_mode("dark" if cfg.get("dark_mode", True) else "light")
        if cfg.get("wakeword_enabled"):
            self.start_wakeword_listener()
        else:
            if self.wake_listener:
                self.wake_listener.stop()
                self.wake_listener = None
            self.status_label.configure(text="Wakeword disabled.")
            try:
                self.orb.set_state("idle")
            except Exception:
                pass


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
