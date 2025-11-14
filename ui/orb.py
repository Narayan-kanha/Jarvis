# ui/orb.py
"""
AnimatedOrb: GIF-based animated orb with a pulsing fallback.
- Robust handling for customtkinter color formats.
- set_state('idle'|'listening'|'thinking'|'speaking'|'error')
- set_on_click(callback)
- set_gif(path) to change GIF at runtime
- destroy()
"""

import os
import time

try:
    import customtkinter as ctk
except Exception:
    ctk = None

import tkinter as tk

try:
    from PIL import Image, ImageTk
    try:
        RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
    except Exception:
        RESAMPLE_LANCZOS = Image.LANCZOS
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageTk = None
    RESAMPLE_LANCZOS = None
    PIL_AVAILABLE = False

# colors and speeds
_STATE_COLORS = {
    "idle": "#0b3d91",
    "listening": "#00d0ff",
    "thinking": "#ffd24d",
    "speaking": "#ffffff",
    "error": "#ff4d4f",
}
_STATE_LABEL_COLORS = {
    "idle": "#bfe7ff",
    "listening": "#00f0ff",
    "thinking": "#ffc94d",
    "speaking": "#ffffff",
    "error": "#ffb3b3",
}
_STATE_SPEED = {
    "idle": 0.6,
    "listening": 1.6,
    "thinking": 0.9,
    "speaking": 2.0,
    "error": 3.0,
}
_DEFAULT_FRAME_DURATION_MS = 100


def _blend_hex_color(hex_from: str, hex_to: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    def h2i(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    a = h2i(hex_from); b = h2i(hex_to)
    out = tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*out)


def _normalize_color_from_ctk(raw):
    """Choose a single color from customtkinter 'fg_color' which may be tuple or 'gray81 gray20' string."""
    if isinstance(raw, (list, tuple)):
        try:
            return str(raw[-1])
        except Exception:
            return str(raw[0])
    if isinstance(raw, str):
        if " " in raw:
            return raw.split()[-1]
        return raw
    return "#000000"


class AnimatedOrb:
    def __init__(self, parent=None, gif_path: str = None, size: int = 120, bg_color: str = None, pack: bool = True):
        self._parent = parent
        self.gif_path = gif_path
        self.size = int(size or 120)
        self._bg_override = bg_color
        self._pack = bool(pack)

        self._state = "idle"
        self._speed_multiplier = 1.0

        # frames/durations
        self._frames = []     # plain list to avoid typing issues
        self._durations = []
        self._frame_index = 0
        self._anim_id = None
        self._anim_running = False

        # pulse fallback
        self._pulse_job = None
        self._pulse_val = 0.0
        self._pulse_dir = 1

        self._on_click = None

        # choose container type
        self._use_ctk = ctk is not None and isinstance(parent, (ctk.CTkFrame, ctk.CTk))
        try:
            if self._use_ctk:
                self._container = ctk.CTkFrame(self._parent, width=self.size, height=self.size, corner_radius=self.size // 2)
            else:
                self._container = tk.Frame(self._parent, width=self.size, height=self.size, bd=0, highlightthickness=0)
        except Exception:
            self._container = tk.Frame(self._parent, width=self.size, height=self.size, bd=0, highlightthickness=0)

        if self._pack:
            try:
                self._container.pack_propagate(False)
                self._container.pack(expand=True, fill="both")
            except Exception:
                pass

        # determine safe bg color
        safe_bg = self._bg_override
        if not safe_bg:
            try:
                raw = self._container.cget("fg_color")
                safe_bg = _normalize_color_from_ctk(raw)
            except Exception:
                safe_bg = "#000000"
        self._safe_bg_color = safe_bg

        # try to load gif
        loaded_gif = False
        if self.gif_path and PIL_AVAILABLE and os.path.exists(self.gif_path):
            try:
                self._load_gif(self.gif_path)
                loaded_gif = bool(self._frames)
            except Exception as exc:
                print("[AnimatedOrb] GIF load failed:", exc)
                loaded_gif = False

        # create visual label
        if loaded_gif:
            try:
                self._label = tk.Label(self._container, bd=0, bg=self._safe_bg_color)
            except Exception:
                self._label = tk.Label(self._container, bd=0)
            try:
                self._label.pack(expand=True, fill="both")
            except Exception:
                pass
            self._anim_running = True
            self._schedule_next_frame()
        else:
            # fallback CTkLabel if available to control text_color
            if ctk is not None:
                try:
                    self._label = ctk.CTkLabel(self._container, text="●",
                                               font=ctk.CTkFont(size=max(18, self.size // 4), weight="bold"),
                                               text_color=_STATE_LABEL_COLORS.get(self._state, "#bfe7ff"))
                    self._label.pack(expand=True)
                except Exception:
                    self._label = tk.Label(self._container, text="●", bd=0, bg=self._safe_bg_color,
                                           font=("TkDefaultFont", max(18, self.size // 4)))
                    self._label.pack(expand=True)
            else:
                self._label = tk.Label(self._container, text="●", bd=0, bg=self._safe_bg_color,
                                       font=("TkDefaultFont", max(18, self.size // 4)))
                try:
                    self._label.pack(expand=True)
                except Exception:
                    pass
            self._anim_running = True
            self._start_pulse_loop()

        # bind click
        try:
            self._label.bind("<ButtonRelease-1>", self._handle_click)
        except Exception:
            pass

        self.set_state("idle")

    # ----- GIF handling -----
    def _load_gif(self, path: str):
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow not available to load GIF.")
        im = Image.open(path)
        frames = []
        durations = []
        try:
            while True:
                frame = im.convert("RGBA").resize((self.size, self.size), RESAMPLE_LANCZOS)
                frames.append(ImageTk.PhotoImage(frame))
                dur = im.info.get("duration", _DEFAULT_FRAME_DURATION_MS) or _DEFAULT_FRAME_DURATION_MS
                durations.append(int(dur))
                im.seek(im.tell() + 1)
        except EOFError:
            pass
        finally:
            try:
                im.close()
            except Exception:
                pass
        self._frames = frames
        self._durations = durations
        self._frame_index = 0

    def _schedule_next_frame(self):
        if not self._anim_running or not self._frames:
            return
        try:
            frame = self._frames[self._frame_index]
            self._label.configure(image=frame)
        except Exception:
            return
        base_ms = self._durations[self._frame_index] if self._durations else _DEFAULT_FRAME_DURATION_MS
        ms = max(10, int(base_ms / max(0.1, self._speed_multiplier)))
        self._frame_index = (self._frame_index + 1) % len(self._frames)
        try:
            if self._anim_id:
                try:
                    self._label.after_cancel(self._anim_id)
                except Exception:
                    pass
            self._anim_id = self._label.after(ms, self._schedule_next_frame)
        except Exception:
            self._anim_id = None

    # ----- pulse fallback -----
    def _start_pulse_loop(self):
        if not self._anim_running:
            return

        def step():
            if not self._anim_running:
                return
            self._pulse_val += 0.03 * (1.5 if self._speed_multiplier > 1 else 1.0) * self._pulse_dir
            if self._pulse_val >= 1.0:
                self._pulse_val = 1.0
                self._pulse_dir = -1
            elif self._pulse_val <= 0.0:
                self._pulse_val = 0.0
                self._pulse_dir = 1

            base_col = _STATE_COLORS.get(self._state, "#0b3d91")
            color = _blend_hex_color(base_col, "#ffffff", self._pulse_val * 0.6)

            try:
                if ctk is not None and isinstance(self._label, ctk.CTkLabel):
                    self._label.configure(text_color=color)
                else:
                    # try several attributes for tk variants
                    self._label.configure(fg=color)
            except Exception:
                try:
                    self._label.configure(foreground=color)
                except Exception:
                    try:
                        self._label.configure(fg=color)
                    except Exception:
                        pass

            try:
                interval = int(max(20, 50 / max(0.1, self._speed_multiplier)))
                self._pulse_job = self._label.after(interval, step)
            except Exception:
                self._pulse_job = None

        step()

    def _stop_pulse_loop(self):
        if self._pulse_job:
            try:
                self._label.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None

    # ----- clicks -----
    def set_on_click(self, cb):
        self._on_click = cb

    def _handle_click(self, event=None):
        if callable(self._on_click):
            try:
                self._on_click()
            except Exception:
                pass

    # ----- public API -----
    def set_state(self, state: str):
        if not state:
            state = "idle"
        state = state.lower()
        if state == self._state:
            self._speed_multiplier = _STATE_SPEED.get(state, 1.0)
            return
        self._state = state
        self._speed_multiplier = _STATE_SPEED.get(state, 1.0)
        bg = _STATE_COLORS.get(state, "#0b3d91")
        label_color = _STATE_LABEL_COLORS.get(state, "#bfe7ff")

        try:
            if self._use_ctk and isinstance(self._container, ctk.CTkFrame):
                try:
                    self._container.configure(fg_color=bg)
                except Exception:
                    try:
                        self._container.configure(bg_color=bg)
                    except Exception:
                        pass
            else:
                self._container.configure(bg=bg)
        except Exception:
            pass

        try:
            if ctk is not None and isinstance(self._label, ctk.CTkLabel):
                self._label.configure(text_color=label_color)
            else:
                try:
                    self._label.configure(fg=label_color)
                except Exception:
                    try:
                        self._label.configure(foreground=label_color)
                    except Exception:
                        pass
        except Exception:
            pass

        if self._frames:
            if self._anim_id:
                try:
                    self._label.after_cancel(self._anim_id)
                except Exception:
                    pass
                self._anim_id = None
            self._schedule_next_frame()
            self._stop_pulse_loop()
        else:
            self._stop_pulse_loop()
            self._start_pulse_loop()

    def set_bg_color(self, hex_color: str):
        try:
            if self._use_ctk and isinstance(self._container, ctk.CTkFrame):
                self._container.configure(fg_color=hex_color)
            else:
                self._container.configure(bg=hex_color)
        except Exception:
            pass

    def set_gif(self, gif_path: str):
        if not gif_path or not PIL_AVAILABLE or not os.path.exists(gif_path):
            return
        try:
            self._anim_running = False
            if self._anim_id:
                try:
                    self._label.after_cancel(self._anim_id)
                except Exception:
                    pass
                self._anim_id = None
            self._stop_pulse_loop()
            self._load_gif(gif_path)
            try:
                try:
                    self._label.destroy()
                except Exception:
                    pass
                self._label = tk.Label(self._container, bd=0, bg=_normalize_color_from_ctk(self._container.cget("fg_color")) if hasattr(self._container, "cget") else "#000000")
                self._label.pack(expand=True, fill="both")
            except Exception:
                pass
            self._anim_running = True
            self._frame_index = 0
            self._schedule_next_frame()
            try:
                self._label.bind("<ButtonRelease-1>", self._handle_click)
            except Exception:
                pass
        except Exception:
            self._frames = []
            self._durations = []

    def destroy(self):
        self._anim_running = False
        if self._anim_id:
            try:
                self._label.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None
        self._stop_pulse_loop()
        try:
            self._label.destroy()
        except Exception:
            pass
        try:
            self._container.destroy()
        except Exception:
            pass

    @property
    def widget(self):
        return self._container

    @property
    def label_widget(self):
        return self._label
