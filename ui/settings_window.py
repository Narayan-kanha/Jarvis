# ui/settings_window.py
"""
SettingsWindow — small modal using customtkinter.
Saves/loads JSON config at config_path.
"""

import os
import json
import threading
from tkinter import messagebox
try:
    import customtkinter as ctk
except Exception:
    ctk = None

DEFAULT_CONFIG = {
    "mic_device": None,
    "idle_model": "tiny",
    "active_model": "medium",
    "screen_model": "base",
    "wakeword_enabled": True,
    "dark_mode": True,
    "porcupine_access_key": None
}


class SettingsWindow:
    def __init__(self, parent, config_path="config.json", on_save=None):
        self.parent = parent
        self.config_path = os.path.abspath(config_path)
        self.on_save = on_save
        self._window = None
        self._widgets = {}
        self._config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    cfg.setdefault(k, v)
                return cfg
            except Exception as exc:
                print("SettingsWindow: load failed, using defaults:", exc)
                return dict(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    def _save_config(self, cfg):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            return True
        except Exception as exc:
            print("SettingsWindow: failed to save:", exc)
            return False

    def show(self):
        if ctk is None:
            messagebox.showerror("Settings", "customtkinter not installed.")
            return
        if self._window and self._window.winfo_exists():
            self._window.lift()
            return

        self._window = ctk.CTkToplevel(self.parent)
        self._window.title("Settings")
        self._window.geometry("480x360")
        self._window.transient(self.parent)
        self._window.grab_set()

        frame = ctk.CTkFrame(self._window)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(frame, text="Microphone device:").pack(anchor="w", pady=(6, 2))
        devices = self._list_mic_devices()
        var_device = ctk.StringVar(value=str(self._config.get("mic_device") or "default"))
        self._widgets["mic_device"] = var_device
        mic_dropdown = ctk.CTkOptionMenu(frame, values=devices if devices else ["default"], variable=var_device)
        mic_dropdown.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Idle (wake) model:").pack(anchor="w", pady=(6, 2))
        var_idle = ctk.StringVar(value=self._config.get("idle_model", DEFAULT_CONFIG["idle_model"]))
        self._widgets["idle_model"] = var_idle
        idle_menu = ctk.CTkOptionMenu(frame, values=["tiny", "base", "small", "medium", "large"], variable=var_idle)
        idle_menu.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Active (command) model:").pack(anchor="w", pady=(6, 2))
        var_active = ctk.StringVar(value=self._config.get("active_model", DEFAULT_CONFIG["active_model"]))
        self._widgets["active_model"] = var_active
        active_menu = ctk.CTkOptionMenu(frame, values=["tiny", "base", "small", "medium", "large"], variable=var_active)
        active_menu.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Screen (OCR) model:").pack(anchor="w", pady=(6, 2))
        var_screen = ctk.StringVar(value=self._config.get("screen_model", DEFAULT_CONFIG["screen_model"]))
        self._widgets["screen_model"] = var_screen
        screen_menu = ctk.CTkOptionMenu(frame, values=["tiny", "base", "small", "medium", "large"], variable=var_screen)
        screen_menu.pack(fill="x", pady=(0, 8))

        var_wake = ctk.BooleanVar(value=bool(self._config.get("wakeword_enabled", True)))
        self._widgets["wakeword_enabled"] = var_wake
        wake_chk = ctk.CTkCheckBox(frame, text="Enable wakeword (Porcupine preferred)", variable=var_wake)
        wake_chk.pack(anchor="w", pady=(8, 8))

        var_dark = ctk.BooleanVar(value=bool(self._config.get("dark_mode", True)))
        self._widgets["dark_mode"] = var_dark
        dark_chk = ctk.CTkCheckBox(frame, text="Dark mode", variable=var_dark, command=self._on_dark_toggle)
        dark_chk.pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(frame, text="Porcupine access key (optional):").pack(anchor="w", pady=(6, 2))
        var_key = ctk.StringVar(value=str(self._config.get("porcupine_access_key") or ""))
        self._widgets["porcupine_access_key"] = var_key
        key_entry = ctk.CTkEntry(frame, textvariable=var_key)
        key_entry.pack(fill="x", pady=(0, 8))

        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", pady=(12, 0))
        save_btn = ctk.CTkButton(btn_frame, text="Save", command=self._on_save, width=110)
        save_btn.pack(side="right", padx=(6, 0))
        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, width=110)
        cancel_btn.pack(side="right")

    def _list_mic_devices(self):
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            mic_inputs = []
            for i, d in enumerate(devs):
                if d.get("max_input_channels", 0) > 0:
                    name = f"{i}: {d.get('name')}"
                    mic_inputs.append(name)
            return mic_inputs
        except Exception:
            return []

    def _on_dark_toggle(self):
        v = self._widgets.get("dark_mode").get()
        try:
            ctk.set_appearance_mode("dark" if v else "light")
        except Exception:
            pass

    def _on_save(self):
        cfg = {}
        mic_val = self._widgets["mic_device"].get()
        if mic_val == "default":
            cfg["mic_device"] = None
        else:
            parts = mic_val.split(":", 1)
            try:
                cfg["mic_device"] = int(parts[0].strip())
            except Exception:
                cfg["mic_device"] = mic_val

        cfg["idle_model"] = self._widgets["idle_model"].get()
        cfg["active_model"] = self._widgets["active_model"].get()
        cfg["screen_model"] = self._widgets["screen_model"].get()
        cfg["wakeword_enabled"] = bool(self._widgets["wakeword_enabled"].get())
        cfg["dark_mode"] = bool(self._widgets["dark_mode"].get())
        cfg["porcupine_access_key"] = self._widgets.get("porcupine_access_key").get()

        ok = self._save_config(cfg)
        if ok:
            messagebox.showinfo("Settings", "Saved settings.")
            if callable(self.on_save):
                try:
                    threading.Thread(target=lambda: self.on_save(cfg), daemon=True).start()
                except Exception:
                    try:
                        self.on_save(cfg)
                    except Exception:
                        pass
            try:
                self._window.destroy()
            except Exception:
                pass
        else:
            messagebox.showerror("Settings", "Failed to save settings.")

    def _on_cancel(self):
        try:
            self._window.destroy()
        except Exception:
            pass
