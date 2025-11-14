# 🧠 Jarvis – Local Desktop AI Assistant  
A fully offline-capable, GPU-accelerated, voice-controlled desktop assistant built with Python, Whisper, customTkinter, and various automation utilities.

Jarvis can:
- Listen continuously (“Hey Jarvis”) or with push-to-talk
- Execute voice commands
- Search Google → DuckDuckGo fallback  
- Download software from the internet  
- Explain what's on your screen (OCR)
- Perform shutdown / restart operations
- Give weather, news, wiki summaries  
- Monitor GPU temperature & usage and auto-protect system  
- Animate a custom `orb.gif` visual interface  
- Minimize into a floating animated orb overlay  

---

## ✨ Features

### 🎙️ Voice Control  
- Whisper-powered speech recognition  
- Three Whisper models:
  - **tiny** for idle listening  
  - **medium** for active queries  
  - **base** for screen explain  
- Wakeword detection: “**Hey Jarvis**”
- Push-to-talk button  
- Adjustable VAD sensitivity  

### 🧠 AI Capabilities  
- Google search → fallback to DuckDuckGo  
- Auto-summary of top result  
- Wikipedia summaries  
- YouTube play command  
- General Q&A  
- System stats  

### 📥 Intelligent Download Assistant  
You can say things like:

> “Jarvis, download Python 3.11.4”

Jarvis will:
1. Search Google  
2. Extract direct download links  
3. Confirm with you  
4. Download with progress bar  

### 🖼️ Screen Explanation  
- Captures and reads your screen with OCR  
- Continues explaining until you press **SPACE**  
- Saves screenshots to `./screen_explain/`  

### 🔥 GPU Safety Monitor  
- Uses NVIDIA NVML (if available)  
- Warns when:
  - Temp ≥ 75°C  
  - Util ≥ 70%  
- Auto-shuts the assistant if:
  - Temp ≥ 80°C  
  - Util ≥ 85%  
  (After voice confirmation)

### 🎧 TTS & SFX  
- TTS via pyttsx3 (offline)
- Optional ElevenLabs voice  
- Sound effects:
  - wake  
  - listen  
  - error  
  - done  

### 🟠 Custom GUI  
Built with **customTkinter**:
- Animated `orb.gif`  
- Dark mode  
- Status, logs, progress bar  
- Buttons: push-to-talk, explain screen, minimize, settings  
- Minimize → floating orb overlay  

---

## 📁 Project Structure

```

Jarvis/
│
├── jarvis_gui.py               # Main application
├── model/                      # Whisper .pt models (auto-downloaded)
│    ├── tiny.pt
│    ├── medium.pt
│    └── base.pt
│
├── assets/
│    ├── sfx/
│    │    ├── wake.wav
│    │    ├── listen.wav
│    │    ├── error.wav
│    │    └── done.wav
│    └── ui/
│         ├── orb.gif
│         └── icon.png
│
├── search_summaries/           # Auto-saved search results
└── screen_explain/             # Saved OCR screenshots

````

---

## 🔧 Installation

### 1. Install Python packages

```sh
pip install torch sounddevice soundfile pygame pyttsx3 numpy pillow
pip install customtkinter mss pytesseract psutil geopy geocoder
pip install beautifulsoup4 duckduckgo-search requests
pip install pynput wikipedia
````

### 2. Install Whisper

```sh
pip install openai-whisper
```

### 3. Optional but recommended

#### NVIDIA GPU monitoring:

```sh
pip install nvidia-ml-py
```

#### OCR (Windows only)

Install **Tesseract OCR**:
[https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)

---

## ▶️ Running Jarvis

```
python jarvis_gui.py
```

On first launch:

* Whisper models will download automatically
* You may be asked to confirm
* Then the GUI will appear

---

## 🎤 Usage Examples

### Wake it up

> “Hey Jarvis”
> *(wait for beep)*

### Ask something

> “Search who invented JavaScript”
> “What is the weather in London?”
> “Explain my screen”
> “Download Python 3.11.4”
> “Open YouTube”
> “Play chill music on YouTube”
> “Shutdown my PC”

### While minimized

Click the floating orb → it reopens and listens instantly.

---

## ⚙️ Configuration

All config values are at the top of `jarvis_gui.py`:

```py
WHISPER_IDLE_MODEL = "tiny"
WHISPER_ACTIVE_MODEL = "medium"
WHISPER_SCREEN_MODEL = "base"

GPU_TEMP_WARN_C = 75
GPU_TEMP_SHUT_C = 80
LISTEN_MODE = "both"
```

You can freely adjust:

* Wakeword sensitivity
* VAD sensitivity
* GPU thresholds
* TTS voice
* Models
* Behavior

---

## 💡 Troubleshooting

### 🔇 Jarvis hears random noise

Increase silence threshold:

```py
RMS_SILENCE_THRESHOLD = 0.015
```

### ⬆️ GPU goes high

This is normal:

* Whisper medium uses the GPU heavily during transcription
* Jarvis will warn you if it's too hot

### ⚠️ Google blocking searches

You’ll see:

```
google-block
```

Jarvis will auto-fallback to DuckDuckGo.

---

## 📜 License

MIT License — free for personal & commercial use.

---

## ❤️ Credits

* Whisper (OpenAI)
* customTkinter
* pytesseract
* pygame
* NVML
* You

---