# ui/window.py
import os
import time
import threading
import tempfile
import webbrowser
import math
import customtkinter as ctk
from tkinter import messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
from ui.orb import AnimatedOrb
from core.recorder import record_seconds_to_wav, record_until_silence
from core.asr import transcribe_with_whisper
from utils.search import google_search_summary, download_via_search
from utils.screen import screen_ocr_loop
from utils.system import gpu_monitor_thread, check_internet

# UI config defaults (can be customized)
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 360
ORB_SIZE = 120
ACCENT_COLOR = "#00d0ff"
DARK_MODE = True
LISTEN_MODE = "both"

class JarvisGUI(ctk.CTk):
    def __init__(self, models: dict, wakeword_engine=None):
        super().__init__()
        self.title("Jarvis")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+80+80")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark" if DARK_MODE else "light")
        ctk.set_default_color_theme("blue")

        # store models and engine
        self.models = models
        self.wakeword_engine = wakeword_engine

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=8)

        self.orb_frame = ctk.CTkFrame(top, width=ORB_SIZE, height=ORB_SIZE, corner_radius=ORB_SIZE//2)
        self.orb_frame.pack(side="left", padx=(6,12))
        self.orb_frame.pack_propagate(False)

        # Use AnimatedOrb with gif if available
        orb_gif = os.path.abspath(os.path.join("assets", "ui", "orb.gif"))
        if os.path.exists(orb_gif):
            self.orb = AnimatedOrb(self.orb_frame, orb_gif, ORB_SIZE)
        else:
            # fallback dot label
            lbl = ctk.CTkLabel(self.orb_frame, text="●", font=ctk.CTkFont(size=36), text_color=ACCENT_COLOR)
            lbl.pack(expand=True)

        status_frame = ctk.CTkFrame(top)
        status_frame.pack(side="left", fill="both", expand=True, padx=6)
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Idle", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(fill="x", pady=(6,4))
        self.mode_label = ctk.CTkLabel(status_frame, text=f"Mode: {LISTEN_MODE}", anchor="w")
        self.mode_label.pack(fill="x")

        mid = ctk.CTkFrame(self); mid.pack(fill="both", expand=True, padx=12, pady=(0,8))
        ctk.CTkLabel(mid, text="Transcribed:").pack(fill="x", padx=6, pady=(6,2))
        self.trans_text = ctk.CTkTextbox(mid, height=70, state="disabled"); self.trans_text.pack(fill="x", padx=6)
        ctk.CTkLabel(mid, text="Assistant:").pack(fill="x", padx=6, pady=(8,2))
        self.assist_text = ctk.CTkTextbox(mid, height=130, state="disabled"); self.assist_text.pack(fill="both", expand=True, padx=6, pady=(0,6))

        pb = ctk.CTkFrame(self); pb.pack(fill="x", padx=12, pady=(0,8))
        self.progress_bar = ctk.CTkProgressBar(pb, width=360); self.progress_bar.set(0); self.progress_bar.pack(side="left", padx=(6,8))
        self.progress_label = ctk.CTkLabel(pb, text=""); self.progress_label.pack(side="left")

        bot = ctk.CTkFrame(self); bot.pack(fill="x", padx=12, pady=(0,12))
        self.speak_btn = ctk.CTkButton(bot, text="Push-to-talk", command=self.manual_listen, width=180); self.speak_btn.pack(side="left", padx=(0,8))
        self.explain_btn = ctk.CTkButton(bot, text="Explain Screen", command=self.start_explain); self.explain_btn.pack(side="left", padx=(0,8))
        self.min_btn = ctk.CTkButton(bot, text="Minimize", command=self.minimize_orb); self.min_btn.pack(side="right")

        menu = ctk.CTkOptionMenu(self, values=["Settings", "Download File", "Quit"], command=self._menu_action)
        menu.place(x=WINDOW_WIDTH-170, y=8)

        self.is_minimized_orb = False
        self.orb_overlay = None

        # start background threads
        if LISTEN_MODE in ("always","both"):
            self._idle_q = []
            self._stop_event = False
            threading.Thread(target=self._idle_recorder_loop, daemon=True).start()
            threading.Thread(target=self._processor_loop, daemon=True).start()

        # GPU monitor thread
        threading.Thread(target=gpu_monitor_thread, args=(self._ask_yes_no,), daemon=True).start()

        # internet check
        if not check_internet():
            self._speak("No internet connection detected. Some features limited.")

    # ---------------- UI callbacks ----------------
    def _ask_yes_no(self, message: str) -> bool:
        event = threading.Event(); result = {"ans": False}
        def _ask():
            try:
                ans = messagebox.askyesno("Jarvis", message)
            except Exception:
                ans = False
            result["ans"] = ans
            event.set()
        self.after(1, _ask)
        event.wait()
        return result["ans"]

    def gui_callback(self, transcribed=None, assistant_text=None, status=None, progress=None, progress_text=None):
        def _u():
            if status:
                self.status_label.configure(text=f"Status: {status}")
            if transcribed is not None:
                self.trans_text.configure(state="normal"); self.trans_text.delete("0.0","end"); self.trans_text.insert("0.0", transcribed); self.trans_text.configure(state="disabled")
            if assistant_text is not None:
                self.assist_text.configure(state="normal"); self.assist_text.insert("end", f"{time.strftime('%H:%M:%S')} — {assistant_text}\n\n"); self.assist_text.see("end"); self.assist_text.configure(state="disabled")
            if progress is not None or progress_text:
                if progress is None:
                    self._show_progress(None, progress_text or "")
                else:
                    self._show_progress(progress, progress_text or "")
        self.after(1, _u)

    def _show_progress(self, frac=None, text=""):
        if frac is None:
            self.progress_bar.set(0.5)
            self.progress_label.configure(text=text)
        else:
            self.progress_bar.set(max(0.0, min(1.0, frac)))
            pct = int((frac or 0)*100)
            self.progress_label.configure(text=f"{pct}% {text}")

    # ---------------- audio / listening ----------------
    def manual_listen(self):
        self.gui_callback(status="Listening")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            p = f.name
        record_seconds_to_wav(6, p, amplify=1.1)
        text = transcribe_with_whisper(self.models["active"], p)
        try: os.remove(p)
        except: pass
        if not text:
            self._speak("I didn't catch that")
            self.gui_callback(transcribed="", assistant_text="No speech detected", status="Idle")
            return
        self.gui_callback(transcribed=text, assistant_text="Thinking...", status="Thinking")
        # handle simple commands inline (or send to handler)
        self._handle_command(text)

    def _idle_recorder_loop(self):
        """
        Continuously record short chunks and store them in a tiny queue (list).
        This is a simplified idle recorder — used by the processor loop below.
        """
        while True:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                p = f.name
            record_seconds_to_wav(3, p, amplify=1.3)
            self._idle_q.append(p)
            # small sleep to avoid tight loop
            time.sleep(0.1)

    def _processor_loop(self):
        """
        Read idle chunks, transcribe with idle model, detect wakeword, then do active listen.
        (This replicates the single-file behavior but modularized.)
        """
        wake_confirm = 0
        while True:
            if not self._idle_q:
                time.sleep(0.1)
                continue
            path = self._idle_q.pop(0)
            try:
                text = transcribe_with_whisper(self.models["idle"], path)
                print("[processor] idle heard:", repr(text))
                if "jarvis" in text.lower() or "hey jarvis" in text.lower():
                    wake_confirm += 1
                else:
                    wake_confirm = 0
                if wake_confirm >= 1:
                    wake_confirm = 0
                    self._speak("Yes?")
                    # active listen
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        ap = f.name
                    record_until_silence(ap, max_duration=20)
                    q = transcribe_with_whisper(self.models["active"], ap)
                    if q:
                        self.gui_callback(transcribed=q, assistant_text="Thinking...", status="Thinking")
                        self._handle_command(q)
                    else:
                        self._speak("I didn't catch that")
                        self.gui_callback(assistant_text="No speech detected", status="Idle")
                    try: os.remove(ap)
                    except: pass
            except Exception as exc:
                print("[processor error]", exc)
            finally:
                try: os.remove(path)
                except: pass

    # ---------------- command handler (simple) ----------------
    def _handle_command(self, text: str):
        q = (text or "").lower().strip()
        # few example commands; you can expand this into a full handler module
        if q.startswith("open "):
            target = q.replace("open ", "", 1).strip()
            webbrowser.open(target if target.startswith("http") else f"https://www.{target}")
            self._speak(f"Opened {target}")
            self.gui_callback(assistant_text=f"Opened {target}", status="Idle")
            return
        if "download" in q:
            threading.Thread(target=download_via_search, args=(text, self.gui_callback, self._ask_yes_no), daemon=True).start()
            return
        if "explain screen" in q or ("explain" in q and "screen" in q):
            threading.Thread(target=screen_ocr_loop, args=(self.gui_callback,), daemon=True).start()
            return
        if "system" in q or "cpu" in q or "memory" in q:
            from utils.system import system_stats
            s = system_stats()
            self._speak(s)
            self.gui_callback(assistant_text=s, status="Idle")
            return
        # generic fallback to search
        summ, fname = google_search_summary(text)
        self._speak(summ[:300])
        self.gui_callback(assistant_text=summ, status="Idle")

    # ---------------- utilities ----------------
    def _speak(self, text: str):
        # lightweight: import local speak to avoid heavy import at module load
        import pyttsx3
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("[speak] err", e)

    # ---------------- screen / window helpers ----------------
    def start_explain(self):
        threading.Thread(target=screen_ocr_loop, args=(self.gui_callback,), daemon=True).start()
        self.gui_callback(assistant_text="Starting screen explanation...", status="Explaining")

    def minimize_orb(self):
        if not self.is_minimized_orb:
            self.withdraw()
            self.is_minimized_orb = True
            self.show_orb_overlay()
        else:
            self.is_minimized_orb = False
            if self.orb_overlay:
                try: self.orb_overlay.destroy()
                except: pass
            self.deiconify()

    def show_orb_overlay(self):
        top = ctk.CTkToplevel(self)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        w = 80; h = 80
        try:
            mx, my = self.winfo_pointerxy(); sw = top.winfo_screenwidth(); sh = top.winfo_screenheight()
        except Exception:
            sw = top.winfo_screenwidth(); sh = top.winfo_screenheight(); mx, my = sw//2, sh//2
        corners = [(20,20), (sw-w-20,20), (20, sh-h-60), (sw-w-20, sh-h-60)]
        def dist(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])
        best = min(corners, key=lambda c: dist((mx,my), c))
        x,y = best
        top.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        frame = ctk.CTkFrame(top, width=w, height=h, corner_radius=40, fg_color=self._fg_color())
        frame.pack_propagate(False); frame.pack(fill="both")
        # use AnimatedOrb inside overlay
        orb_gif = os.path.abspath(os.path.join("assets","ui","orb.gif"))
        if os.path.exists(orb_gif):
            AnimatedOrb(frame, orb_gif, 56)
        else:
            lbl = ctk.CTkLabel(frame, text="●", font=ctk.CTkFont(size=36), text_color=ACCENT_COLOR); lbl.pack(expand=True)
        self.orb_overlay = top
        def on_click(e=None):
            try: top.destroy()
            except: pass
            self.is_minimized_orb = False
            self.deiconify()
            threading.Thread(target=self._restore_and_listen, daemon=True).start()
        frame.bind("<ButtonRelease-1>", on_click)

    def _restore_and_listen(self):
        self.gui_callback(assistant_text="Ready — listening...", status="Listening")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            p = f.name
        record_until_silence(p, max_duration=20)
        q = transcribe_with_whisper(self.models["active"], p)
        try: os.remove(p)
        except: pass
        if not q:
            self._speak("I didn't catch that")
            self.gui_callback(transcribed="", assistant_text="No speech detected", status="Idle"); return
        self.gui_callback(transcribed=q, assistant_text="Thinking...", status="Thinking"); self._handle_command(q)

    def _fg_color(self):
        return "#1a1a1a" if DARK_MODE else "#ffffff"

    def _menu_action(self, choice):
        if choice == "Settings":
            messagebox.showinfo("Settings","Edit config in main.py and restart.")
        elif choice == "Download File":
            threading.Thread(target=self._download_dialog, daemon=True).start()
        elif choice == "Quit":
            self.on_quit()

    def _download_dialog(self):
        url = simpledialog.askstring("Download","Enter file URL:")
        if not url: return
        dest = filedialog.asksaveasfilename(initialdir=os.path.join(os.path.expanduser("~"), "Downloads"), initialfile=os.path.basename(url))
        if not dest:
            dest = os.path.join(os.path.expanduser("~"), "Downloads", os.path.basename(url))
        threading.Thread(target=download_via_search, args=(url, self.gui_callback, self._ask_yes_no), daemon=True).start()

    def on_quit(self):
        if messagebox.askokcancel("Quit","Quit Jarvis?"):
            os._exit(0)
