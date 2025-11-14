"""
ui/orb.py — AnimatedOrb widget for Jarvis

Features:
 - Load and animate an animated GIF (PIL required).
 - Fallback to a pulsing CTkLabel if GIF not available or load fails.
 - Robust handling of customTkinter "fg_color" (tuple, "gray81 gray20", etc).
 - State API: set_state('idle'|'listening'|'thinking'|'speaking'|'error')
 - Works with both tkinter labels and customtkinter frames/labels.
 - Accepts positional args (parent, gif_path, size) or keywords (parent/parent_widget, gif_path, size, bg_color).
 - Click callback support via set_on_click(callable).
 - Safe to call from GUI thread only (uses .after scheduling).

Usage examples:
    orb = AnimatedOrb(parent_frame, "./assets/ui/orb.gif", 120)
    orb.set_state("listening")
    orb.set_on_click(lambda: print("orb clicked"))
    orb.destroy()
"""

from typing import List, Optional, Callable, Tuple
import os
import math
import time

# GUI libs
try:
    import customtkinter as ctk
except Exception:
    ctk = None  # we will still try to work with tk widgets

import tkinter as tk

# PIL (optional — used for GIF animation)
try:
    from PIL import Image, ImageTk
    # Pillow resampling compatibility
    try:
        RESAMPLE_LANCZOS = Image.Resampling.LANCZOS  # Pillow >= 9
    except Exception:
        RESAMPLE_LANCZOS = Image.LANCZOS
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageTk = None
    RESAMPLE_LANCZOS = None
    PIL_AVAILABLE = False

# ---------------------------------------------------------------------
# Configuration: colors, speed multipliers per state
# ---------------------------------------------------------------------
_STATE_COLORS = {
    "idle": "#0b3d91",       # deep blue
    "listening": "#00d0ff",  # cyan/teal
    "thinking": "#ffd24d",   # yellow
    "speaking": "#ffffff",   # white
    "error": "#ff4d4f",      # red
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

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _blend_hex_color(hex_from: str, hex_to: str, t: float) -> str:
    """
    Simple linear blend between two hex colors. t in [0,1].
    """
    t = max(0.0, min(1.0, t))
    def h2i(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    a = h2i(hex_from); b = h2i(hex_to)
    out = tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*out)

def _normalize_color_from_ctk(raw) -> str:
    """
    customtkinter CTkFrame.cget('fg_color') may return:
      - a tuple/list like ('#xyz','#abc')
      - a string of two tokens 'gray81 gray20'
      - a single color string like '#rrggbb' or 'gray20'
    This picks a reliable single color (prefer darker/more stable).
    """
    if isinstance(raw, (list, tuple)):
        # many CTk versions return (light, dark) — pick the last (usually dark)
        try:
            val = raw[-1]
            return str(val)
        except Exception:
            return str(raw[0])
    if isinstance(raw, str):
        if " " in raw:
            # pick the last token (usually the darker one)
            return raw.split()[-1]
        return raw
    # fallback
    return "#000000"

# ---------------------------------------------------------------------
# AnimatedOrb class
# ---------------------------------------------------------------------
class AnimatedOrb:
    def __init__(
        self,
        parent=None,
        gif_path: Optional[str] = None,
        size: int = 120,
        bg_color: Optional[str] = None,
        pack: bool = True,
    ):
        """
        Create an AnimatedOrb.

        Parameters:
          parent: parent TK/CTk container (positional or keyword 'parent_widget' supported by callers).
          gif_path: path to an animated GIF (optional).
          size: integer pixel size (width and height).
          bg_color: optional background color override (single color string like '#rrggbb').
          pack: whether to pack the internal container automatically. If False, caller must geometry-manage.
        """
        self._parent = parent
        self.gif_path = gif_path
        self.size = int(size or 120)
        self._bg_color_override = bg_color
        self._pack = bool(pack)

        # state
        self._state = "idle"
        self._speed_multiplier = 1.0

        # gif frames
        self._frames: List[ImageTk.PhotoImage] = []
        self._durations: List[int] = []
        self._frame_index = 0
        self._anim_id = None
        self._anim_running = False

        # fallback pulse
        self._pulse_job = None
        self._pulse_val = 0.0
        self._pulse_dir = 1

        # click callback
        self._on_click: Optional[Callable[[], None]] = None

        # create container: prefer CTkFrame (if customtkinter available), else tk.Frame
        self._use_ctk = ctk is not None and isinstance(parent, (ctk.CTkFrame, ctk.CTk))
        try:
            if self._use_ctk:
                self._container = ctk.CTkFrame(self._parent, width=self.size, height=self.size, corner_radius=self.size // 2)
            else:
                self._container = tk.Frame(self._parent, width=self.size, height=self.size, bd=0, highlightthickness=0)
        except Exception:
            # last-resort plain tk.Frame
            self._container = tk.Frame(self._parent, width=self.size, height=self.size, bd=0, highlightthickness=0)

        # geometry-manage if requested
        if self._pack:
            try:
                self._container.pack_propagate(False)
                self._container.pack(expand=True, fill="both")
            except Exception:
                # caller will manage geometry
                pass

        # determine a safe background color for tk.Label when needed
        safe_bg = None
        if self._bg_color_override:
            safe_bg = self._bg_color_override
        else:
            # try to read CTkFrame fg_color if CTkFrame used
            try:
                raw = self._container.cget("fg_color")
                safe_bg = _normalize_color_from_ctk(raw)
            except Exception:
                # fallback default
                safe_bg = "#000000"

        self._safe_bg_color = safe_bg

        # Attempt to load GIF frames (if path given and Pillow available)
        loaded_gif = False
        if self.gif_path and PIL_AVAILABLE and os.path.exists(self.gif_path):
            try:
                self._load_gif(self.gif_path)
                loaded_gif = bool(self._frames)
            except Exception as exc:
                # don't crash on GIF load failure — fallback to dot
                print(f"[AnimatedOrb] GIF load failed: {exc}")
                loaded_gif = False

        # Create visual element: prefer tk.Label for animated images (tk supports PhotoImage),
        # otherwise CTkLabel fallback for pulsing colored dot.
        if loaded_gif:
            # tk.Label is preferred for displaying PhotoImage frames reliably
            try:
                self._label = tk.Label(self._container, bd=0, bg=self._safe_bg_color)
            except Exception:
                # fallback to plain Label without bg
                self._label = tk.Label(self._container, bd=0)
            try:
                self._label.pack(expand=True, fill="both")
            except Exception:
                pass
            self._anim_running = True
            self._schedule_next_frame()
        else:
            # fallback: CTkLabel (if available) to allow text_color control; else tk.Label
            if ctk is not None:
                try:
                    self._label = ctk.CTkLabel(self._container, text="●",
                                               font=ctk.CTkFont(size=max(18, self.size // 4), weight="bold"),
                                               text_color=_STATE_LABEL_COLORS.get(self._state, "#bfe7ff"))
                    self._label.pack(expand=True)
                except Exception:
                    # fallback to tk
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
            # start pulsing
            self._anim_running = True
            self._start_pulse_loop()

        # bind click events for both tk and ctk labels
        try:
            self._label.bind("<ButtonRelease-1>", self._handle_click)
        except Exception:
            try:
                # CTkLabel uses .bind as well
                self._label.bind("<ButtonRelease-1>", self._handle_click)
            except Exception:
                pass

        # apply initial state visuals
        self.set_state("idle")

    # ---------------- GIF handling ----------------
    def _load_gif(self, path: str) -> None:
        """
        Load frames/durations from animated GIF into self._frames/self._durations.
        Uses PIL.Image.
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow (PIL) not available to load GIF.")
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
        except Exception as exc:
            # re-raise to let caller decide fallback
            raise
        finally:
            try:
                im.close()
            except Exception:
                pass
        self._frames = frames
        self._durations = durations
        self._frame_index = 0

    def _schedule_next_frame(self):
        """
        Display next frame and schedule the next call using after().
        Respects self._speed_multiplier.
        """
        if not self._anim_running or not self._frames:
            return
        try:
            frame = self._frames[self._frame_index]
            self._label.configure(image=frame)
        except Exception:
            # label may not accept image — bail
            return

        base_ms = self._durations[self._frame_index] if self._durations else _DEFAULT_FRAME_DURATION_MS
        # apply speed multiplier (higher multiplier => faster animation)
        ms = max(10, int(base_ms / max(0.1, self._speed_multiplier)))
        self._frame_index = (self._frame_index + 1) % len(self._frames)
        # schedule next
        try:
            if self._anim_id:
                # clear previous if somehow set
                try:
                    self._label.after_cancel(self._anim_id)
                except Exception:
                    pass
            self._anim_id = self._label.after(ms, self._schedule_next_frame)
        except Exception:
            # if after fails, stop animation
            self._anim_id = None

    # ---------------- Pulse fallback ----------------
    def _start_pulse_loop(self):
        """Start pulsing loop for fallback dot mode."""
        if not self._anim_running:
            return

        def step():
            if not self._anim_running:
                return
            # move value
            self._pulse_val += 0.03 * (1.5 if self._speed_multiplier > 1 else 1.0) * self._pulse_dir
            if self._pulse_val >= 1.0:
                self._pulse_val = 1.0
                self._pulse_dir = -1
            elif self._pulse_val <= 0.0:
                self._pulse_val = 0.0
                self._pulse_dir = 1

            # compute label color based on state and pulse value
            base_col = _STATE_COLORS.get(self._state, "#0b3d91")
            # blend towards white for brightness
            color = _blend_hex_color(base_col, "#ffffff", self._pulse_val * 0.6)

            # set color depending on label type
            try:
                # ctk label uses text_color
                if ctk is not None and isinstance(self._label, ctk.CTkLabel):
                    self._label.configure(text_color=color)
                else:
                    self._label.configure(fg=color)  # attempt
            except Exception:
                try:
                    self._label.configure(foreground=color)
                except Exception:
                    try:
                        self._label.configure(fg=color)
                    except Exception:
                        pass

            # schedule next
            try:
                interval = int(max(20, 50 / max(0.1, self._speed_multiplier)))
                self._pulse_job = self._label.after(interval, step)
            except Exception:
                self._pulse_job = None

        # start immediately
        step()

    def _stop_pulse_loop(self):
        if self._pulse_job:
            try:
                self._label.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None

    # ---------------- Click handling ----------------
    def set_on_click(self, cb: Optional[Callable[[], None]]):
        """Set callback to be invoked when user clicks the orb."""
        self._on_click = cb

    def _handle_click(self, event=None):
        if callable(self._on_click):
            try:
                self._on_click()
            except Exception:
                # never raise from UI event
                pass

    # ---------------- Public API ----------------
    def set_state(self, state: str) -> None:
        """
        Set orb visual state. Known states:
          'idle', 'listening', 'thinking', 'speaking', 'error'
        """
        if not state:
            state = "idle"
        state = state.lower()
        if state == self._state:
            # still update multiplier in case it changed externally
            self._speed_multiplier = _STATE_SPEED.get(state, 1.0)
            return

        self._state = state
        # update speed and colors
        self._speed_multiplier = _STATE_SPEED.get(state, 1.0)
        bg = _STATE_COLORS.get(state, "#0b3d91")
        label_text_color = _STATE_LABEL_COLORS.get(state, "#bfe7ff")

        # set container background where possible
        try:
            if self._use_ctk and isinstance(self._container, ctk.CTkFrame):
                # CTkFrame uses fg_color style
                try:
                    self._container.configure(fg_color=bg)
                except Exception:
                    # some CTk versions accept bg_color
                    try:
                        self._container.configure(bg_color=bg)
                    except Exception:
                        pass
            else:
                # plain tk.Frame supports bg
                self._container.configure(bg=bg)
        except Exception:
            pass

        # apply label color for fallback mode
        try:
            if ctk is not None and isinstance(self._label, ctk.CTkLabel):
                self._label.configure(text_color=label_text_color)
            else:
                # tk.Label variants: foreground / fg
                try:
                    self._label.configure(fg=label_text_color)
                except Exception:
                    try:
                        self._label.configure(foreground=label_text_color)
                    except Exception:
                        try:
                            self._label.configure(fg=label_text_color)
                        except Exception:
                            pass
        except Exception:
            pass

        # tune animation behavior
        if self._frames:
            # for GIF animation, speed is adjusted by multiplier via _schedule_next_frame
            # ensure we reschedule with updated speed
            if self._anim_id:
                try:
                    self._label.after_cancel(self._anim_id)
                except Exception:
                    pass
                self._anim_id = None
            self._schedule_next_frame()
            # stop any fallback pulse
            self._stop_pulse_loop()
        else:
            # restart / adjust pulse loop
            self._stop_pulse_loop()
            self._start_pulse_loop()

    def set_bg_color(self, hex_color: str) -> None:
        """Override the container background color (single hex or named color)."""
        try:
            if self._use_ctk and isinstance(self._container, ctk.CTkFrame):
                self._container.configure(fg_color=hex_color)
            else:
                self._container.configure(bg=hex_color)
        except Exception:
            pass

    def set_gif(self, gif_path: str) -> None:
        """
        Replace current visual with a new GIF. Attempts to load and switch into GIF mode;
        if fails, keeps existing mode.
        """
        if not gif_path or not PIL_AVAILABLE or not os.path.exists(gif_path):
            return
        try:
            # stop any existing animation/pulse
            self._anim_running = False
            if self._anim_id:
                try:
                    self._label.after_cancel(self._anim_id)
                except Exception:
                    pass
                self._anim_id = None
            self._stop_pulse_loop()

            # load new frames
            self._load_gif(gif_path)
            # replace label with tk.Label if necessary (tk needed for PhotoImage)
            try:
                # destroy existing label widget
                try:
                    self._label.destroy()
                except Exception:
                    pass
                # create a tk.Label to show images
                self._label = tk.Label(self._container, bd=0, bg=_normalize_color_from_ctk(self._container.cget("fg_color")) if hasattr(self._container, "cget") else "#000000")
                self._label.pack(expand=True, fill="both")
            except Exception:
                # if we cannot create a tk.Label, just keep old label (best-effort)
                pass

            # start animating
            self._anim_running = True
            self._frame_index = 0
            self._schedule_next_frame()
            # rebind click
            try:
                self._label.bind("<ButtonRelease-1>", self._handle_click)
            except Exception:
                pass
        except Exception:
            # revert to previous behavior on failure
            self._frames = []
            self._durations = []

    def destroy(self) -> None:
        """Stop animation/pulse and destroy widgets."""
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

    # convenience properties
    @property
    def widget(self):
        """Return the container widget (for geometry management or inspection)."""
        return self._container

    @property
    def label_widget(self):
        """Return the internal label widget (where images/text are drawn)."""
        return self._label

# End of file
