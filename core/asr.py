# core/asr.py
"""
Whisper model loader + transcription helpers.
- ensure_model_with_prompt(model_name): prompts (tk messagebox) to download if missing.
- transcribe_with_whisper(model, path, language='en'): returns text or ''.
"""

import os
import shutil
import whisper
import torch
import tkinter as tk
from tkinter import messagebox

MODEL_SAVE_DIR = os.path.abspath("./model")
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)


def ensure_tk_root_for_dialogs():
    """Ensure a tk root exists for messagebox calls when called outside a GUI."""
    if tk._default_root is None:
        root = tk.Tk()
        root.withdraw()
        return True, root
    return False, tk._default_root


def try_copy_model_from_cache(model_name: str) -> bool:
    """Best-effort copy of .pt file from common caches into MODEL_SAVE_DIR."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".cache", "whisper", f"{model_name}.pt"),
        os.path.join(home, ".cache", "huggingface", "hub"),
    ]
    for root_dir in [os.path.join(home, ".cache", "huggingface", "hub"), os.path.join(home, ".cache", "whisper")]:
        if os.path.isdir(root_dir):
            for root, _, files in os.walk(root_dir):
                for f in files:
                    try:
                        if f.lower().startswith(model_name.lower()) and f.lower().endswith(".pt"):
                            candidates.append(os.path.join(root, f))
                    except Exception:
                        pass
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
    Ensure a whisper model exists. If not in MODEL_SAVE_DIR, asks user to download.
    Returns a model instance from whisper.load_model.
    """
    target = os.path.join(MODEL_SAVE_DIR, f"{model_name}.pt")
    if os.path.exists(target):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return whisper.load_model(model_name, device=device)

    created, root = ensure_tk_root_for_dialogs()
    try:
        answer = messagebox.askyesno(
            "Model required",
            f"Whisper model '{model_name}' not found in {MODEL_SAVE_DIR}.\nDownload now? (May be large)"
        )
    finally:
        if created:
            try:
                root.destroy()
            except Exception:
                pass

    if not answer:
        raise RuntimeError(f"Model {model_name} missing and user declined download")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    m = whisper.load_model(model_name, device=device)

    # best-effort copy from cache into MODEL_SAVE_DIR
    try_copy_model_from_cache(model_name)
    return m


def transcribe_with_whisper(model, path: str, language: str = "en") -> str:
    """Transcribe file using given whisper model instance. Returns text or ''."""
    try:
        res = model.transcribe(path, language=language)
        return res.get("text", "").strip()
    except Exception as e:
        print("[asr] transcribe error:", e)
        return ""
