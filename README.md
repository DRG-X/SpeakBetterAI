# 🎙️ SpeakBetter AI

> **Real-Time Pronunciation & Voice Feedback Coach**  
> A production-grade portfolio project built for Speech AI internship applications.

---

## 📸 Overview

SpeakBetter AI listens to you speak a target sentence, transcribes it with Whisper, scores your pronunciation out of 100, highlights your mistakes word-by-word, and plays back the correct pronunciation using a neural TTS voice — all in a polished web UI.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎙️ Voice Recording | In-browser microphone input via Gradio |
| 🧠 AI Transcription | `faster-whisper` (CTranslate2-optimised Whisper) |
| 🏆 Pronunciation Scoring | Multi-factor score /100 with letter grade |
| 🔍 Word-Level Analysis | Missing / incorrect / extra word detection |
| 🔊 TTS Playback | Coqui TTS neural voice (gTTS fallback) |
| 🎲 Sentence Bank | 30+ sentences across 4 difficulty tiers |
| 📈 Session Tracking | Attempt history + best score in-session |
| 🌐 Accent Mode | Groundwork for multi-accent support |
| 🚀 HF Spaces Ready | Deployable to Hugging Face Spaces out of the box |

---

## 🧪 Tech Stack

```
Frontend        Gradio Blocks (custom CSS dark UI)
STT             faster-whisper (base model, CTranslate2)
TTS             Coqui TTS — tts_models/en/ljspeech/vits
Scoring         difflib + custom fuzzy word matching
Audio I/O       soundfile, numpy
Language        Python 3.10+
Deployment      Local / Hugging Face Spaces
```

---

## 📁 Project Structure

```
speakbetter_ai/
│── app.py            ← Main Gradio app + UI layout + event wiring
│── stt.py            ← Speech-to-Text pipeline (faster-whisper)
│── tts_engine.py     ← Text-to-Speech engine (Coqui + gTTS fallback)
│── scoring.py        ← Pronunciation scoring & word-diff analysis
│── utils.py          ← Sentence bank, session stats, helpers
│── requirements.txt  ← Pinned dependencies
│── README.md         ← This file
```

---

## 🚀 Setup & Run

### Prerequisites

- Python 3.10 or higher
- `pip` package manager
- Microphone access in your browser
- ~2–3 GB disk space (Whisper + Coqui models download on first run)

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/speakbetter-ai.git
cd speakbetter-ai
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The first install downloads PyTorch (~700MB) and the Coqui TTS model (~200MB). Subsequent runs use the local cache.

### 4. Run the app

```bash
python app.py
```

Open `http://localhost:7860` in your browser.

---

## 🌐 Deploy to Hugging Face Spaces

1. Create a new Space at [huggingface.co/spaces](https://huggingface.co/spaces)
2. Set SDK to **Gradio**, Python 3.10, CPU Basic hardware
3. Push your code:

```bash
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/speakbetter-ai
git push space main
```

4. Spaces will auto-install `requirements.txt` and launch `app.py`

> Models are downloaded and cached on first cold start (~3–5 minutes). Subsequent starts are fast.

---

## 🎮 Demo Usage

1. **Pick a difficulty** — choose Beginner, Intermediate, Advanced, or Tech
2. **Click 🎲 Random Sentence** to load a practice sentence
3. **Click the microphone** — record yourself reading the sentence
4. **Click ⚡ Analyse Pronunciation**
5. Review your:
   - **Transcript** — what Whisper heard
   - **Score** — out of 100 with letter grade
   - **Mistake analysis** — missing / wrong / extra words
   - **Feedback** — coaching summary
6. **Listen** to the correct pronunciation playback
7. **Retry** to improve your score

---

## 🧠 Scoring Algorithm

The scoring engine uses a multi-factor blended approach:

```
1. Sequence similarity (difflib SequenceMatcher) — 30% weight
2. Word-level diff analysis — 70% weight:
   - Missing word:       -8 pts
   - Wrong word:         -6 pts
   - Partial match:      -3 pts (fuzzy threshold 60–85%)
   - Extra word:         -2 pts

Final = clamp(0.70 × word_score + 0.30 × seq_similarity, 0, 100)
```

**Grade thresholds:** A ≥ 90 | B ≥ 80 | C ≥ 70 | D ≥ 60 | F < 60

---

## 🔮 Future Upgrades

- [ ] **Phoneme-level analysis** — use `phonemizer` + forced alignment (wav2vec2) for per-phoneme error detection
- [ ] **Real accent model** — fine-tune a classifier for American / British / Australian accent scoring
- [ ] **Prosody feedback** — detect speaking rate, pitch variation, and stress patterns
- [ ] **Leaderboard** — multi-user score tracking with a lightweight SQLite backend
- [ ] **Mobile PWA** — wrap in a Progressive Web App for mobile pronunciation practice
- [ ] **Multi-language support** — extend to French, Spanish, Mandarin sentence banks
- [ ] **Whisper large-v3** — option for higher accuracy on GPU hardware

---

## 💼 Why This Is Relevant to Speech AI Startups

This project demonstrates hands-on experience with the **exact stack** modern speech AI teams use:

| Startup Need | This Project |
|---|---|
| STT pipeline | faster-whisper (production-grade Whisper) |
| TTS synthesis | Coqui VITS (open-source neural TTS) |
| Audio processing | soundfile, numpy, librosa |
| Phonetic comparison | difflib + custom fuzzy word alignment |
| Product shipping | End-to-end MVP in a single weekend |
| Cloud deployment | Hugging Face Spaces compatible |
| Clean engineering | Modular, documented, error-handled code |

---

## 📄 License

MIT License — free to use, fork, and build upon.

---

_Built with ❤️ as a Speech AI internship portfolio project._
