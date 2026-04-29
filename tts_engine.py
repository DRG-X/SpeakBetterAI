"""
tts_engine.py — Text-to-Speech module for SpeakBetter AI
Primary: Coqui TTS (high quality neural voice)
Fallback: gTTS (Google TTS, requires internet, still great quality)

Model is loaded once and reused for low latency.
"""

import os
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# TTS Backend Selection
# ---------------------------------------------------------------------------
# We try Coqui first. If it fails (env issue, missing model), we fall back
# to gTTS which works great on Hugging Face Spaces.
# ---------------------------------------------------------------------------

_tts_backend: str = "none"
_coqui_tts = None


def _init_coqui() -> bool:
    """
    Attempt to initialize Coqui TTS.
    Returns True on success, False on failure.
    """
    global _coqui_tts, _tts_backend

    try:
        from TTS.api import TTS as CoquiTTS

        print("[TTS] Initializing Coqui TTS — downloading model if needed (~200MB first run) ...")
        # VITS model: fast inference, high quality, single-speaker
        _coqui_tts = CoquiTTS(model_name="tts_models/en/ljspeech/vits", progress_bar=True)
        _tts_backend = "coqui"
        print("[TTS] Coqui TTS ready.")
        return True

    except Exception as e:
        print(f"[TTS] Coqui TTS init failed: {e}")
        return False


def _init_gtts() -> bool:
    """
    Attempt to set up gTTS as fallback backend.
    Returns True on success.
    """
    global _tts_backend
    try:
        import gtts  # noqa: F401
        _tts_backend = "gtts"
        print("[TTS] Using gTTS fallback backend.")
        return True
    except ImportError:
        print("[TTS] gTTS not available either. TTS disabled.")
        return False


def _ensure_backend():
    """
    Lazily initialize TTS backend on first use.
    Tries Coqui → gTTS → disabled.
    """
    if _tts_backend != "none":
        return  # Already initialized

    if not _init_coqui():
        _init_gtts()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def speak_text(text: str) -> str | None:
    """
    Convert text to speech and save to a temporary WAV/MP3 file.

    Args:
        text: The sentence to synthesize.

    Returns:
        Path to the generated audio file, or None on failure.
    """
    if not text or not text.strip():
        return None

    _ensure_backend()

    text = text.strip()

    if _tts_backend == "coqui":
        return _speak_coqui(text)
    elif _tts_backend == "gtts":
        return _speak_gtts(text)
    else:
        print("[TTS] No backend available. Cannot synthesize speech.")
        return None


def _speak_coqui(text: str) -> str | None:
    """Generate speech using Coqui VITS model."""
    try:
        # Create a persistent temp file (Gradio needs the file to exist after return)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

        _coqui_tts.tts_to_file(text=text, file_path=output_path)
        print(f"[TTS] Coqui synthesis complete: {output_path}")
        return output_path

    except Exception as e:
        print(f"[TTS] Coqui synthesis error: {e}")
        return None


def _speak_gtts(text: str) -> str | None:
    """Generate speech using Google TTS fallback."""
    try:
        from gtts import gTTS

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        output_path = tmp.name
        tmp.close()

        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(output_path)
        print(f"[TTS] gTTS synthesis complete: {output_path}")
        return output_path

    except Exception as e:
        print(f"[TTS] gTTS synthesis error: {e}")
        return None


def get_backend_name() -> str:
    """Return the name of the currently active TTS backend."""
    _ensure_backend()
    return _tts_backend
