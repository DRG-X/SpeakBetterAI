"""
stt.py — Speech-to-Text module for SpeakBetter AI
Uses faster-whisper for efficient, accurate transcription.
Model is loaded once at module level to avoid repeated initialization costs.
"""

import os
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
# "base" gives a great speed/accuracy balance for a portfolio demo.
# Switch to "small" or "medium" for higher accuracy at the cost of speed.
WHISPER_MODEL_SIZE = "base"
COMPUTE_TYPE = "int8"   # Use "float16" on CUDA GPU, "int8" for CPU efficiency

# Singleton model instance — loaded once, reused across all transcriptions.
_model: WhisperModel | None = None


def _load_model() -> WhisperModel:
    """
    Lazily load the Whisper model on first call.
    Subsequent calls return the cached instance.
    """
    global _model
    if _model is None:
        print(f"[STT] Loading faster-whisper model: {WHISPER_MODEL_SIZE} ...")
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",          # Change to "cuda" if GPU is available
            compute_type=COMPUTE_TYPE,
        )
        print("[STT] Model loaded successfully.")
    return _model


def transcribe_audio(audio_path: str | Path) -> str:
    """
    Transcribe a recorded audio file to text using faster-whisper.

    Args:
        audio_path: Path to the audio file (wav, mp3, m4a, etc.)

    Returns:
        Transcribed text as a single stripped string.
        Returns empty string on error.
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        print(f"[STT] ERROR: Audio file not found: {audio_path}")
        return ""

    try:
        model = _load_model()

        # faster-whisper uses ffmpeg internally — handles webm, wav, mp3, ogg.
        # Windows: winget install ffmpeg  OR  choco install ffmpeg
        segments, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
        )

        # Collect all segment texts
        transcript_parts = [segment.text for segment in segments]
        transcript = " ".join(transcript_parts).strip()

        print(f"[STT] Transcribed: '{transcript}' | Language: {info.language} | Confidence: {info.language_probability:.2f}")
        return transcript

    except Exception as e:
        print(f"[STT] Transcription error: {e}")
        return ""


def transcribe_gradio_audio(audio_tuple) -> str:
    """
    Helper for Gradio's microphone input, which provides audio as a
    (sample_rate, numpy_array) tuple. Saves to a temp WAV file first.

    Args:
        audio_tuple: (sample_rate, np.ndarray) from Gradio mic component.

    Returns:
        Transcribed text string.
    """
    if audio_tuple is None:
        return ""

    import numpy as np
    import soundfile as sf

    sample_rate, audio_data = audio_tuple

    # Ensure correct dtype for soundfile
    if audio_data.dtype != np.float32:
        audio_data = audio_data.astype(np.float32)
        # Normalize int16 range to float
        if audio_data.max() > 1.0:
            audio_data = audio_data / 32768.0

    # Write to a temporary WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    sf.write(tmp_path, audio_data, sample_rate)

    transcript = transcribe_audio(tmp_path)

    # Clean up temp file
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    return transcript
