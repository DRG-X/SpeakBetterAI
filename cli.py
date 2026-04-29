"""
cli.py — SpeakBetter AI Terminal App
Run: python cli.py
"""

import os
import sys
import tempfile
import random
import threading
import time

# ── dependency check ──────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
except ImportError:
    print("[ERROR] Missing audio deps. Run:  pip install sounddevice soundfile numpy")
    sys.exit(1)

from stt import transcribe_audio
from tts_engine import speak_text
from scoring import score_pronunciation, format_mistakes_display
from utils import SENTENCE_BANK, get_all_difficulties, SessionStats

# ── colours (Windows-safe with colorama fallback) ─────────────────────────────
try:
    import colorama; colorama.init()
    C = {
        "cyan":   "\033[96m", "green":  "\033[92m", "yellow": "\033[93m",
        "red":    "\033[91m", "white":  "\033[97m", "grey":   "\033[90m",
        "bold":   "\033[1m",  "reset":  "\033[0m",
    }
except ImportError:
    C = {k: "" for k in ["cyan","green","yellow","red","white","grey","bold","reset"]}


def c(color, text):
    return f"{C.get(color,'')}{text}{C['reset']}"


# ── recording ─────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000   # Whisper works best at 16kHz


def record_until_enter() -> str | None:
    """
    Record from mic until user presses Enter.
    Returns path to a temp WAV file, or None on error.
    """
    frames = []
    recording = threading.Event()
    recording.set()

    def _capture():
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            while recording.is_set():
                chunk, _ = stream.read(1024)
                frames.append(chunk.copy())

    thread = threading.Thread(target=_capture, daemon=True)
    thread.start()

    print(c("grey", "  ● Recording… press ") + c("yellow", "Enter") + c("grey", " to stop"))

    # Ticker so user sees something is happening
    def _tick():
        i = 0
        symbols = ["◐","◓","◑","◒"]
        while recording.is_set():
            print(f"\r  {c('red', symbols[i % 4])} {i}s", end="", flush=True)
            time.sleep(1)
            i += 1
    tick_thread = threading.Thread(target=_tick, daemon=True)
    tick_thread.start()

    input()          # blocks until Enter
    recording.clear()
    thread.join()
    print("\r  " + c("green", "✔ Stopped.") + "          ")

    if not frames:
        print(c("red", "  No audio captured."))
        return None

    audio = np.concatenate(frames, axis=0)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, SAMPLE_RATE)
    return tmp.name


# ── display helpers ───────────────────────────────────────────────────────────

GRADE_COLOR = {"A": "green", "B": "green", "C": "yellow", "D": "yellow", "F": "red"}

def score_bar(score: int, width: int = 40) -> str:
    filled = int((score / 100) * width)
    bar    = "█" * filled + "░" * (width - filled)
    col    = "green" if score >= 80 else "yellow" if score >= 55 else "red"
    return c(col, f"[{bar}]") + f" {score}/100"


def print_header():
    os.system("cls" if os.name == "nt" else "clear")
    print(c("cyan", c("bold", """
  ███████╗██████╗ ███████╗ █████╗ ██╗  ██╗
  ██╔════╝██╔══██╗██╔════╝██╔══██╗██║ ██╔╝
  ███████╗██████╔╝█████╗  ███████║█████╔╝
  ╚════██║██╔═══╝ ██╔══╝  ██╔══██║██╔═██╗
  ███████║██║     ███████╗██║  ██║██║  ██╗
  ╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
""")))
    print(c("grey", "  Pronunciation & Voice Feedback Coach  •  terminal edition\n"))


def print_divider(char="─", width=58):
    print(c("grey", char * width))


def pick_sentence() -> tuple[str, str]:
    """Interactive sentence picker. Returns (sentence, difficulty)."""
    difficulties = get_all_difficulties()[1:]   # skip 'all'
    print(c("bold", "\n  Choose difficulty:"))
    for i, d in enumerate(difficulties, 1):
        count = len(SENTENCE_BANK[d])
        print(f"    {c('cyan', str(i))}. {d.capitalize():<14} {c('grey', f'({count} sentences)')}")
    print(f"    {c('cyan', str(len(difficulties)+1))}. Random  {c('grey','(any difficulty)')}")

    while True:
        choice = input(c("grey", "\n  Enter number: ")).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(difficulties):
                diff = difficulties[idx]
                sentence = random.choice(SENTENCE_BANK[diff])
                return sentence, diff
            elif idx == len(difficulties):
                diff = random.choice(difficulties)
                sentence = random.choice(SENTENCE_BANK[diff])
                return sentence, diff
        print(c("red", "  Invalid choice, try again."))


def print_result(transcript: str, target: str):
    result = score_pronunciation(target, transcript)

    print_divider()
    print(c("bold", "\n  📊 RESULTS\n"))

    # Score bar
    print(f"  {score_bar(result.score)}")
    grade_col = GRADE_COLOR.get(result.grade, "white")
    print(f"  Grade: {c(grade_col, c('bold', result.grade))}   {result.feedback_summary}\n")

    # Transcript vs target
    print(c("grey", "  Target  : ") + c("white",  target))
    print(c("grey", "  You said: ") + c("cyan",   transcript))

    # Mistake breakdown
    mistakes_text = format_mistakes_display(result)
    if "No mistakes" not in mistakes_text:
        print()
        # Strip markdown for terminal
        clean = (mistakes_text
                 .replace("**Missing words:**", c("red",    "  Missing  :"))
                 .replace("**Incorrect words:**",c("yellow", "  Incorrect:"))
                 .replace("**Extra words:**",   c("grey",   "  Extra    :"))
                 .replace("`", ""))
        print(clean)

    print(f"\n  Similarity: {result.similarity_pct:.1f}%  •  "
          f"Words spoken: {result.word_count_spoken}/{result.word_count_target}")
    print_divider()
    return result


# ── main loop ─────────────────────────────────────────────────────────────────

def main():
    print_header()
    print(c("grey", "  Loading models (first run may take a minute)…\n"))

    # Pre-load Whisper model so first attempt isn't slow
    from stt import _load_model
    _load_model()

    stats = SessionStats()

    while True:
        print_divider("═")
        sentence, diff = pick_sentence()

        print(f"\n  {c('grey','Difficulty:')} {c('cyan', diff.capitalize())}")
        print_divider()
        print(f"\n  {c('bold','Say this sentence:')}\n")
        print(f"    {c('white', c('bold', sentence))}\n")
        print_divider()

        # Record
        print(f"\n  {c('green','Ready!')} Press {c('yellow','Enter')} to start recording…")
        input()

        audio_path = record_until_enter()

        if audio_path is None:
            print(c("red", "  Recording failed. Try again.\n"))
            continue

        # Transcribe
        print(f"\n  {c('grey','Transcribing…')}")
        transcript = transcribe_audio(audio_path)
        try: os.remove(audio_path)
        except: pass

        if not transcript.strip():
            print(c("red", "\n  ❌ No speech detected. Please try again.\n"))
            continue

        # Score + display
        result = print_result(transcript, sentence)
        stats.record_attempt(sentence, transcript, result.score, result.grade)

        # TTS playback
        print(f"\n  {c('grey','Playing correct pronunciation…')}")
        tts_path = speak_text(sentence)
        if tts_path:
            try:
                data, sr = sf.read(tts_path)
                sd.play(data, sr)
                sd.wait()
                os.remove(tts_path)
            except Exception as e:
                print(c("yellow", f"  (Could not play audio: {e})"))

        # Session stats
        print(f"\n  Session: {stats.attempt_count} attempt(s)  •  "
              f"Best score: {c('green', str(stats.best_score))}/100  "
              f"{stats.trend_emoji()}")

        # Next action
        print(f"\n  {c('bold','What next?')}")
        print(f"    {c('cyan','r')} – Retry same sentence")
        print(f"    {c('cyan','n')} – New sentence")
        print(f"    {c('cyan','h')} – Session history")
        print(f"    {c('cyan','q')} – Quit")

        while True:
            action = input(c("grey", "\n  Choice: ")).strip().lower()
            if action == "r":
                break          # same sentence — outer while restarts with same sentence trick
            elif action == "n":
                sentence = None
                break
            elif action == "h":
                print_divider()
                print(stats.format_history_md()
                      .replace("**", "").replace("_", "").replace("`", ""))
                print_divider()
            elif action == "q":
                print(c("cyan", "\n  Thanks for practising! Keep going. 🎙️\n"))
                sys.exit(0)
            else:
                print(c("red", "  Type r / n / h / q"))

        if action == "r":
            # Re-run same sentence — jump back without repicking
            while True:
                print_divider("═")
                print(f"\n  {c('grey','Difficulty:')} {c('cyan', diff.capitalize())}")
                print_divider()
                print(f"\n  {c('bold','Same sentence:')}\n")
                print(f"    {c('white', c('bold', sentence))}\n")
                print_divider()
                print(f"\n  {c('green','Ready!')} Press {c('yellow','Enter')} to start recording…")
                input()
                audio_path = record_until_enter()
                if not audio_path:
                    continue
                print(f"\n  {c('grey','Transcribing…')}")
                transcript = transcribe_audio(audio_path)
                try: os.remove(audio_path)
                except: pass
                if not transcript.strip():
                    print(c("red", "\n  ❌ No speech detected.\n"))
                    continue
                result = print_result(transcript, sentence)
                stats.record_attempt(sentence, transcript, result.score, result.grade)
                tts_path = speak_text(sentence)
                if tts_path:
                    try:
                        data, sr = sf.read(tts_path)
                        sd.play(data, sr); sd.wait()
                        os.remove(tts_path)
                    except: pass
                print(f"\n  Best score: {c('green', str(stats.best_score))}/100  {stats.trend_emoji()}")
                action2 = input(c("grey", "\n  r=retry  n=new  q=quit: ")).strip().lower()
                if action2 != "r":
                    break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("cyan", "\n\n  Goodbye! 🎙️\n"))
