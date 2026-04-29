"""
utils.py — Utility helpers for SpeakBetter AI

Includes:
  - Practice sentence bank (categorised by difficulty)
  - Random sentence selection
  - Retry tracking
  - Score history helpers
  - Accent mode placeholder (groundwork for future feature)
"""

import random
from dataclasses import dataclass, field
from datetime import datetime

# ---------------------------------------------------------------------------
# Practice Sentence Bank
# ---------------------------------------------------------------------------

SENTENCE_BANK: dict[str, list[str]] = {
    "beginner": [
        "The cat sat on the mat.",
        "She sells seashells by the seashore.",
        "Please speak clearly and slowly.",
        "How much wood would a woodchuck chuck?",
        "The quick brown fox jumps over the lazy dog.",
        "Good morning, how are you today?",
        "I would like a cup of coffee please.",
        "The sun sets in the west.",
    ],
    "intermediate": [
        "Whether the weather is fine or whether the weather is not.",
        "Peter Piper picked a peck of pickled peppers.",
        "Around the rugged rocks the ragged rascal ran.",
        "Red lorry, yellow lorry, red lorry, yellow lorry.",
        "Unique New York, unique New York, you know you need unique New York.",
        "She saw Sherif's shoes on the sofa but was her sister Sherif's?",
        "Artificial intelligence is transforming every industry on the planet.",
        "I scream, you scream, we all scream for ice cream.",
    ],
    "advanced": [
        "The sixth sick sheik's sixth sheep's sick.",
        "Pad kid poured curd pulled cod — say that ten times fast.",
        "Pronunciation is the production of sounds used to make meaningful words.",
        "Thorough articulation of every phoneme is essential in broadcast journalism.",
        "The phonological structure of a language determines its prosodic patterns.",
        "Statistical machine learning models can now surpass human-level speech recognition.",
        "Speech synthesis technology has advanced remarkably since the early days of concatenation.",
    ],
    "tech": [
        "Machine learning models require large amounts of labelled training data.",
        "Natural language processing enables computers to understand human speech.",
        "The transformer architecture revolutionised the field of deep learning.",
        "Automatic speech recognition converts spoken words into written text.",
        "Voice assistants use wake word detection to conserve battery life.",
        "Prosody refers to the rhythm, stress, and intonation patterns of speech.",
    ],
}

ALL_DIFFICULTIES = list(SENTENCE_BANK.keys())


def get_random_sentence(difficulty: str = "all") -> tuple[str, str]:
    """
    Return a random practice sentence.

    Args:
        difficulty: "beginner" | "intermediate" | "advanced" | "tech" | "all"

    Returns:
        (sentence, difficulty_label)
    """
    if difficulty == "all" or difficulty not in SENTENCE_BANK:
        # Pick from entire bank
        diff = random.choice(ALL_DIFFICULTIES)
    else:
        diff = difficulty

    sentence = random.choice(SENTENCE_BANK[diff])
    return sentence, diff


def get_all_difficulties() -> list[str]:
    """Return list of available difficulty keys."""
    return ["all"] + ALL_DIFFICULTIES


# ---------------------------------------------------------------------------
# Session / Retry Tracking
# ---------------------------------------------------------------------------

@dataclass
class SessionStats:
    """
    Tracks attempt history for the current session.
    Designed to be passed around via Gradio State.
    """
    attempts: list[dict] = field(default_factory=list)
    best_score: int = 0
    current_sentence: str = ""

    def record_attempt(self, sentence: str, transcript: str, score: int, grade: str):
        """Log one pronunciation attempt."""
        self.attempts.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "sentence": sentence,
            "transcript": transcript,
            "score": score,
            "grade": grade,
        })
        if score > self.best_score:
            self.best_score = score

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def last_scores(self, n: int = 5) -> list[int]:
        """Return the last n scores."""
        return [a["score"] for a in self.attempts[-n:]]

    def trend_emoji(self) -> str:
        """Show a simple trend indicator based on last 2 scores."""
        scores = self.last_scores(2)
        if len(scores) < 2:
            return ""
        if scores[-1] > scores[-2]:
            return "📈"
        if scores[-1] < scores[-2]:
            return "📉"
        return "➡️"

    def format_history_md(self) -> str:
        """Format attempt history as Markdown for display."""
        if not self.attempts:
            return "_No attempts yet this session._"

        lines = [f"**Session History** ({self.attempt_count} attempts, best: {self.best_score}/100)\n"]
        for i, a in enumerate(reversed(self.attempts[-8:]), 1):
            lines.append(
                f"{i}. `{a['timestamp']}` — Score: **{a['score']}/100** ({a['grade']})  \n"
                f"   Said: _{a['transcript']}_"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Accent Mode Placeholder
# ---------------------------------------------------------------------------

ACCENT_MODES = {
    "General American": {
        "description": "Standard US broadcast accent — the default target.",
        "language_code": "en-US",
        "note": "Best supported by current TTS models.",
    },
    "British RP": {
        "description": "Received Pronunciation — standard British English.",
        "language_code": "en-GB",
        "note": "Supported via gTTS fallback with lang='en-gb'.",
    },
    "Australian": {
        "description": "General Australian English.",
        "language_code": "en-AU",
        "note": "Placeholder — full support coming soon.",
    },
    "Indian English": {
        "description": "Indian subcontinent English accent.",
        "language_code": "en-IN",
        "note": "Placeholder — full support coming soon.",
    },
}


def get_accent_info(accent_name: str) -> dict:
    """Return metadata for a given accent mode."""
    return ACCENT_MODES.get(accent_name, ACCENT_MODES["General American"])


def get_available_accents() -> list[str]:
    """Return list of accent mode names for UI dropdown."""
    return list(ACCENT_MODES.keys())


# ---------------------------------------------------------------------------
# Score bar helpers
# ---------------------------------------------------------------------------

def score_to_color_class(score: int) -> str:
    """Return a CSS-compatible color name for a score value."""
    if score >= 90:
        return "green"
    if score >= 75:
        return "lime"
    if score >= 60:
        return "orange"
    if score >= 40:
        return "yellow"
    return "red"


def build_score_bar(score: int, width: int = 40) -> str:
    """
    Build a simple ASCII/Unicode progress bar for terminal debugging.
    Not used in Gradio UI — kept for CLI testing.
    """
    filled = int((score / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score}/100"
