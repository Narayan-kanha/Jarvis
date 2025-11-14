# core/asr.py
import os
import shutil
import tempfile
import tkinter as tk
from tkinter import messagebox
import whisper
import torch

MODEL_SAVE_DIR = os.path.abspath("./model")
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

def ensure_tk_root_for_dialogs():
    """Make sure a Tk root exists so messagebox works when called outside GUI."""
    if tk._default_root is None:
        root = tk.Tk()
        root.withdraw()
        return True, root
    return False, tk._default_root

def try_copy_model_from_cache(model_name: str) -> bool:
    """
    Attempt to copy a .pt file from common whisper/huggingface caches to MODEL_SAVE_DIR.
    Best-effort.
    """
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".cache", "whisper", f"{model_name}.pt"),
        os.path.join(home, ".cache", "huggingface", "hub")
    ]
    for root_dir in [os.path.join(home, ".cache", "huggingface", "hub"), os.path.join(home, ".cache", "whisper")]:
        if os.path.isdir(root_dir):
            for root, _, files in os.walk(root_dir):
                for f in files:
                    if f.lower().startswith(model_name.lower()) and f.lower().endswith(".pt"):
                        candidates.append(os.path.join(root, f))
    for c in candidates:
        if os.path.exists(c):
            try:
                dest = os.path.join(MODEL_SAVE_DIR, f"{model_name}.pt")
                shutil.copyfile(c, dest)
                return True
            except Exception:
                return False
    return False

def ensure_model_with_prompt(model_name: str):
    """
    Ensure whisper model exists. If not, prompt user to download via whisper.load_model.
    Returns the loaded model instance.
    """
    target = os.path.join(MODEL_SAVE_DIR, f"{model_name}.pt")
    if os.path.exists(target):
        # whisper.load_model will still use cache but returning the model is fine
        return whisper.load_model(model_name, device="cuda" if torch.cuda.is_available() else "cpu")

    created, root = ensure_tk_root_for_dialogs()
    try:
        res = messagebox.askyesno("Model required",
                                  f"Whisper model '{model_name}' not found in {MODEL_SAVE_DIR}.\nDownload now? (May be large)")
    finally:
        if created:
            try: root.destroy()
            except: pass

    if not res:
        raise RuntimeError(f"Model {model_name} is required but user declined download")

    # Download through whisper (default cache)
    model = whisper.load_model(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
    # Try to copy a .pt file from cache into MODEL_SAVE_DIR (best-effort)
    try_copy_model_from_cache(model_name)
    return model

def transcribe_with_whisper(model, path: str, language: str = "en") -> str:
    """Transcribe using the given whisper model instance. Returns text or '' on failure."""
    try:
        res = model.transcribe(path, language=language)
        return res.get("text", "").strip()
    except Exception as e:
        print("[asr] transcribe error:", e)
        return ""
