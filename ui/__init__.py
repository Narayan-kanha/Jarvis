# ui/__init__.py
from .orb import AnimatedOrb
from .settings_window import SettingsWindow

# JarvisGUI is in ui.window (import lazily in main) but export if you want
try:
    from .window import JarvisGUI
except Exception:
    JarvisGUI = None

__all__ = ["AnimatedOrb", "SettingsWindow", "JarvisGUI"]
