---

# 🧠 Jarvis — Modular Local Desktop AI Assistant

A clean, fully-modular, GPU-accelerated, voice-controlled offline assistant powered by **Whisper**, **customTkinter**, **Porcupine wakeword**, **OCR**, and robust system tools.

Jarvis now uses a **structured multi-file architecture**, an **animated orb UI**, and a **clean separation** between ASR, GUI, command handling, and utilities.

---

# ✨ What’s New (Modular Edition)

✔ Fully split into **modules**
✔ Beautiful **Animated Orb (`orb.gif`)**
✔ Proper **floating orb overlay**
✔ **ASR isolated** in `core/asr.py`
✔ **Wakeword** (optional Porcupine) in `core/wakeword.py`
✔ **Audio recorder** in `core/recorder.py`
✔ **Search, OCR, system, GPU monitor** in `utils/`
✔ GUI rewritten cleanly in `ui/window.py`
✔ All logic cleanly organized — no more 2,500-line monster files

---

# 📁 Project Structure (New Modular Layout)

```
Jarvis/
│
├── main.py                     # Entry point - loads models, starts GUI
│
├── core/                       # ASR + wakeword + recording
│   ├── __init__.py
│   ├── asr.py                  # Whisper loading + transcription
│   ├── recorder.py             # Audio recording helpers
│   └── wakeword.py             # Porcupine wakeword engine (optional)
│
├── ui/                         # User Interface
│   ├── __init__.py
│   ├── orb.py                  # Animated GIF orb class
│   └── window.py               # Main GUI using customTkinter
│
├── utils/                      # Tools & helpers
│   ├── __init__.py
│   ├── search.py               # Google + DuckDuckGo + downloader
│   ├── screen.py               # Screen capture + OCR
│   └── system.py               # GPU monitor + system stats + internet check
│
├── model/                      # Whisper models auto-saved here
│   ├── tiny.pt
│   ├── medium.pt
│   └── base.pt
│
├── assets/
│   ├── sfx/                    # UI sound effects
│   │   ├── wake.wav
│   │   ├── listen.wav
│   │   ├── error.wav
│   │   └── done.wav
│   └── ui/
│       ├── orb.gif            # Animated orb
│       └── icon.png           # Window icon
│
├── search_summaries/           # Auto-saved search summaries
└── screen_explain/             # OCR screenshot dumps
```

---

# 🚀 Features

## 🎙️ Voice Assistant

* Whisper-powered speech recognition:

  * `tiny` → idle / always listening
  * `medium` → active conversation
  * `base` → OCR speech
* Optional **Porcupine wakeword** (“Jarvis”)
* Push-to-talk button
* Adjustable VAD & silence detection

---

## 🔎 Smart Search + Downloads

### “Search for how hot the sun is”

✔ Google search → fallback DuckDuckGo summary
✔ Auto-saves text summary

### “Download Python 3.12”

✔ Scrapes top Google result
✔ Extracts direct download links
✔ Confirms via GUI
✔ Downloads with progress bar

---

## 🖥️ Screen Explanation (OCR)

* Capture screen every second
* Extract text with Tesseract
* Read aloud
* Stop anytime by pressing **SPACE**
* Saves all frames to `screen_explain/`

---

## 🔊 Voice & Sound Feedback

* TTS (pyttsx3 — fully offline)
* Sound effects:

  * wake
  * listen
  * error
  * done

You can customize voices, ElevenLabs optional.

---

## 🔥 GPU Safety Monitor

* Real-time reading (via NVML)
* Warns when:

  * Temp ≥ 75°C
  * Util ≥ 70%
* Asks user before auto-shutting:

  * Temp ≥ 80°C
  * Util ≥ 85%

---

## 🧩 New GUI System

* Built with **customTkinter**
* Uses modular `ui/window.py`
* Displays:

  * Status
  * Transcript
  * Assistant output
  * Progress bar
* **Animated orb from orb.gif**
* Minimize → **floating orb overlay**

  * Always on top
  * Clicking → opens GUI & starts listening

---

# 🔧 Installation

## 1. Install Dependencies

### Core:

```sh
pip install torch sounddevice soundfile pygame pyttsx3 numpy pillow
pip install customtkinter beautifulsoup4 requests
pip install mss pytesseract psutil pynput
pip install geopy geocoder wikipedia duckduckgo-search
```

### Whisper

```sh
pip install openai-whisper
```

### Optional

GPU monitor:

```sh
pip install nvidia-ml-py
```

Porcupine wakeword:

```sh
pip install pvporcupine
```

For OCR on Windows:
Install Tesseract:
[https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)

---

# ▶️ Running Jarvis

### Launch:

```
python main.py
```

On first run:

* Models will download automatically
* GUI opens with animated orb
* Idle listener starts (if enabled)

---

# 🎤 Voice Examples

### Wake Up

> “Hey Jarvis”

### Commands

> “Search who built the Burj Khalifa”
> “Open YouTube”
> “Play lo-fi music on YouTube”
> “Download VSCode”
> “What’s my system usage?”
> “Explain my screen”
> “Shutdown the PC”

### Minimized Mode

* Click floating orb → GUI reopens → Jarvis listens instantly

---

# ⚙️ Configuration

Inside `main.py` or module configs:

```py
WHISPER_IDLE_MODEL = "tiny"
WHISPER_ACTIVE_MODEL = "medium"
WHISPER_SCREEN_MODEL = "base"

GPU_TEMP_WARN_C = 75
GPU_TEMP_SHUT_C = 80

LISTEN_MODE = "both"   # 'always', 'push', 'both'
PICOVOICE_ACCESS_KEY = None
```

You can adjust:

* Models
* Wakeword engine
* Sensitivity
* Voice
* Interface

---

# 💡 Troubleshooting

### Random Wakeword Triggers

Lower noise sensitivity in `core/recorder.py`:

```py
rms_threshold = 0.015
```

### GPU Spikes

Whisper medium uses GPU heavily — this is normal.

### Google Blocked

Jarvis switches to DuckDuckGo automatically.

---

# 📜 License

MIT License — free for personal & commercial use.

---

# ❤️ Credits

* Whisper (OpenAI)
* customTkinter
* Porcupine (Picovoice)
* pytesseract
* NVML
* pygame
* You

