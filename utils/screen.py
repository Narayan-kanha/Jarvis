# utils/screen.py
import time
import mss
from PIL import Image
try:
    import pytesseract
except Exception:
    pytesseract = None

def capture_screen_image():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.rgb)

def screen_ocr_loop(gui_cb=None):
    if not pytesseract:
        if gui_cb:
            gui_cb(assistant_text="pytesseract not installed; screen explain unavailable", status="Idle")
        return
    try:
        from pynput import keyboard
    except Exception:
        if gui_cb:
            gui_cb(assistant_text="pynput not available; screen explain needs it", status="Idle")
        return
    stop = {"flag": False}
    def on_press(key):
        try:
            if key == keyboard.Key.space:
                stop["flag"] = True
                return False
        except Exception:
            pass
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    frame = 0; last = ""
    while not stop["flag"]:
        img = capture_screen_image()
        ts = time.strftime("%Y%m%d_%H%M%S")
        text = pytesseract.image_to_string(img).strip()
        desc = f"Text on screen: {text[:800]}" if text else "No text detected on screen."
        if desc != last:
            last = desc
            if gui_cb:
                gui_cb(transcribed="", assistant_text="(screen) " + desc)
        frame += 1
        time.sleep(1.0)
    listener.stop()
    if gui_cb:
        gui_cb(transcribed="", assistant_text="Screen explanation stopped", status="Idle")
