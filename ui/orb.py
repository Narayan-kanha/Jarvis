# ui/orb.py
import tkinter as tk
from PIL import Image, ImageTk
import customtkinter as ctk

class AnimatedOrb:
    """
    Animated GIF orb to be used inside CTk frames or toplevels.
    parent_widget: CTk/Frame to attach to
    gif_path: path to orb.gif
    size: pixel size
    """
    def __init__(self, parent_widget, gif_path: str, size: int):
        self.parent = parent_widget
        self.gif_path = gif_path
        self.size = size
        self.frames, self.durations = self._load_gif_frames(gif_path)
        self.frame_index = 0
        self.label = tk.Label(self.parent, bd=0, highlightthickness=0, bg=self._resolve_bg(parent_widget))
        if self.frames:
            self.label.pack(expand=True, fill="both")
            self._animate()
        else:
            fallback = ctk.CTkLabel(self.parent, text="●", font=ctk.CTkFont(size=48, weight="bold"), text_color="#00d0ff")
            fallback.pack(expand=True)

    def _resolve_bg(self, widget):
        try:
            fg = widget.cget("fg_color")
            if isinstance(fg, (tuple, list)):
                return fg[1]
            return fg
        except Exception:
            return "#000000"

    def _load_gif_frames(self, path):
        frames = []
        durations = []
        try:
            with Image.open(path) as img:
                while True:
                    resized = img.resize((self.size, self.size), Image.Resampling.LANCZOS)
                    frames.append(ImageTk.PhotoImage(resized.convert("RGBA")))
                    durations.append(img.info.get("duration", 80))
                    img.seek(img.tell() + 1)
        except EOFError:
            pass
        except Exception as e:
            print("[AnimatedOrb] error loading gif:", e)
        return frames, durations

    def _animate(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        duration = self.durations[self.frame_index]
        self.label.configure(image=frame)
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.parent.after(duration or 80, self._animate)
