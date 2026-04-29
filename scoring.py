"""
scoring.py — Pronunciation scoring and comparison engine for SpeakBetter AI

Uses a multi-factor approach:
  1. Sequence similarity (difflib SequenceMatcher)
  2. Word-level diff analysis (missing / incorrect / extra words)
  3. Fuzzy per-word matching (handles minor mispronunciations)
  4. Weighted final score /100

Returns a rich result dict consumed by app.py for display.
"""

import re
import difflib
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Fuzzy word matching helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _word_similarity(a: str, b: str) -> float:
    """
    Return similarity ratio (0.0–1.0) between two words using
    difflib's SequenceMatcher. Handles minor typos / mispronunciations.
    """
    return difflib.SequenceMatcher(None, a, b).ratio()


def _find_best_match(word: str, candidates: list[str]) -> tuple[str | None, float]:
    """
    Find the best fuzzy match for `word` among `candidates`.
    Returns (best_candidate, similarity_ratio).
    """
    if not candidates:
        return None, 0.0

    best_word = None
    best_score = 0.0
    for candidate in candidates:
        score = _word_similarity(word, candidate)
        if score > best_score:
            best_score = score
            best_word = candidate

    return best_word, best_score


# ---------------------------------------------------------------------------
# Core scoring dataclass
# ---------------------------------------------------------------------------

@dataclass
class PronunciationResult:
    """Structured result returned by score_pronunciation()."""
    score: int                          # 0–100 final score
    similarity_pct: float               # Raw sequence similarity %
    missed_words: list[str] = field(default_factory=list)
    incorrect_words: list[str] = field(default_factory=list)   # [(spoken, expected)]
    extra_words: list[str] = field(default_factory=list)
    word_count_target: int = 0
    word_count_spoken: int = 0
    grade: str = ""                     # Letter grade A/B/C/D/F
    feedback_summary: str = ""          # Human-readable one-liner

    def to_display_dict(self) -> dict:
        """Convert to a flat dict for Gradio UI display."""
        return {
            "score": self.score,
            "similarity_pct": round(self.similarity_pct, 1),
            "missed_words": self.missed_words,
            "incorrect_words": self.incorrect_words,
            "extra_words": self.extra_words,
            "grade": self.grade,
            "feedback_summary": self.feedback_summary,
            "word_count_target": self.word_count_target,
            "word_count_spoken": self.word_count_spoken,
        }


# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------

# Similarity thresholds for per-word judgement
CORRECT_THRESHOLD = 0.85     # ≥ this → correct (minor accent/typo forgiven)
PARTIAL_THRESHOLD = 0.60     # ≥ this → partially correct (half penalty)

# Score deductions
DEDUCT_MISSING_WORD = 8      # Per missing word
DEDUCT_WRONG_WORD = 6        # Per wrong word (full mismatch)
DEDUCT_PARTIAL_WORD = 3      # Per partially matched word
DEDUCT_EXTRA_WORD = 2        # Per extra word (insertion)

# Grade boundaries
GRADE_THRESHOLDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]


def _assign_grade(score: int) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _generate_feedback(score: int, missed: list, incorrect: list, extra: list) -> str:
    """Generate a concise human-readable feedback summary."""
    if score == 100:
        return "🎉 Perfect! Flawless pronunciation."
    if score >= 90:
        return "🌟 Excellent! Almost perfect — tiny refinements needed."
    if score >= 80:
        return "👍 Great job! A few words to polish."
    if score >= 70:
        return "📈 Good effort! Focus on the highlighted words."
    if score >= 55:
        return "💪 Keep practicing — you're getting there!"
    return "🔁 Try again slowly, word by word."


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_pronunciation(target: str, spoken: str) -> PronunciationResult:
    """
    Compare spoken text against the target sentence and produce a
    detailed pronunciation score.

    Args:
        target:  The sentence the user was supposed to say.
        spoken:  The transcribed text of what the user actually said.

    Returns:
        PronunciationResult with score, grade, and detailed word analysis.
    """
    # --- Normalise both inputs -----------------------------------------------
    norm_target = _normalize(target)
    norm_spoken = _normalize(spoken)

    target_words = norm_target.split()
    spoken_words = norm_spoken.split()

    # --- Sequence-level similarity -------------------------------------------
    seq_similarity = difflib.SequenceMatcher(
        None, norm_target, norm_spoken
    ).ratio() * 100  # as percentage

    # --- Word-level diff using difflib opcodes --------------------------------
    sm = difflib.SequenceMatcher(None, target_words, spoken_words)
    opcodes = sm.get_opcodes()

    missed_words: list[str] = []
    incorrect_words: list[tuple[str, str]] = []   # (spoken, expected)
    extra_words: list[str] = []
    partial_count = 0
    deductions = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue  # perfect match, no penalty

        elif tag == "delete":
            # Words in target not spoken at all
            for w in target_words[i1:i2]:
                missed_words.append(w)
                deductions += DEDUCT_MISSING_WORD

        elif tag == "insert":
            # Extra words spoken not in target
            for w in spoken_words[j1:j2]:
                extra_words.append(w)
                deductions += DEDUCT_EXTRA_WORD

        elif tag == "replace":
            # Words differ — check if fuzzy match saves them
            t_chunk = target_words[i1:i2]
            s_chunk = spoken_words[j1:j2]

            # Align by the longer chunk
            max_len = max(len(t_chunk), len(s_chunk))
            for idx in range(max_len):
                t_word = t_chunk[idx] if idx < len(t_chunk) else None
                s_word = s_chunk[idx] if idx < len(s_chunk) else None

                if t_word is None:
                    extra_words.append(s_word)
                    deductions += DEDUCT_EXTRA_WORD
                elif s_word is None:
                    missed_words.append(t_word)
                    deductions += DEDUCT_MISSING_WORD
                else:
                    sim = _word_similarity(t_word, s_word)
                    if sim >= CORRECT_THRESHOLD:
                        # Close enough — minor accent, no penalty
                        pass
                    elif sim >= PARTIAL_THRESHOLD:
                        # Partial match — small penalty
                        partial_count += 1
                        deductions += DEDUCT_PARTIAL_WORD
                        incorrect_words.append((s_word, t_word))
                    else:
                        # Full mismatch
                        deductions += DEDUCT_WRONG_WORD
                        incorrect_words.append((s_word, t_word))

    # --- Edge case: no audio / empty transcript ------------------------------
    if not spoken_words:
        return PronunciationResult(
            score=0,
            similarity_pct=0.0,
            missed_words=target_words,
            incorrect_words=[],
            extra_words=[],
            word_count_target=len(target_words),
            word_count_spoken=0,
            grade="F",
            feedback_summary="❌ No speech detected. Please record again.",
        )

    # --- Compute final score -------------------------------------------------
    # Base 100, subtract deductions, floor at 0
    raw_score = max(0, 100 - deductions)

    # Blend with sequence similarity to smooth edge cases
    # 70% word-diff score + 30% sequence similarity
    blended_score = int(0.70 * raw_score + 0.30 * seq_similarity)
    final_score = max(0, min(100, blended_score))

    grade = _assign_grade(final_score)
    feedback = _generate_feedback(final_score, missed_words, incorrect_words, extra_words)

    return PronunciationResult(
        score=final_score,
        similarity_pct=seq_similarity,
        missed_words=missed_words,
        incorrect_words=incorrect_words,
        extra_words=extra_words,
        word_count_target=len(target_words),
        word_count_spoken=len(spoken_words),
        grade=grade,
        feedback_summary=feedback,
    )


def format_mistakes_display(result: PronunciationResult) -> str:
    """
    Format the mistake analysis into a clean, readable Markdown string
    for display in the Gradio UI.
    """
    lines = []

    if not result.missed_words and not result.incorrect_words and not result.extra_words:
        return "✅ No mistakes detected!"

    if result.missed_words:
        words = ", ".join(f"`{w}`" for w in result.missed_words)
        lines.append(f"**Missing words:** {words}")

    if result.incorrect_words:
        pairs = ", ".join(f"`{spoken}` → `{expected}`" for spoken, expected in result.incorrect_words)
        lines.append(f"**Incorrect words:** {pairs}")

    if result.extra_words:
        words = ", ".join(f"`{w}`" for w in result.extra_words)
        lines.append(f"**Extra words:** {words}")

    return "\n\n".join(lines)
