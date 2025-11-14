"""
demo_orb.py
Test all orb states without running main Jarvis.
"""

import tkinter as tk
import customtkinter as ctk
from ui.orb import AnimatedOrb
import time

STATES = ["idle", "listening", "thinking", "speaking", "error"]

def run():
    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.geometry("350x350")
    root.title("Orb Demo")

    frame = ctk.CTkFrame(root, width=200, height=200, corner_radius=20)
    frame.pack(expand=True)

    orb = AnimatedOrb(
        parent=frame,
        gif_path="./assets/ui/orb.gif",
        size=160,
        pack=True
    )

    def cycle_states(idx=0):
        state = STATES[idx % len(STATES)]
        print(f"[DEMO] Setting state: {state}")
        orb.set_state(state)
        root.after(1500, lambda: cycle_states(idx + 1))

    cycle_states()
    root.mainloop()


if __name__ == "__main__":
    run()
