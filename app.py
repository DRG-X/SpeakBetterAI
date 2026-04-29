"""
app.py — SpeakBetter AI
Mic recording handled via custom HTML/JS to avoid Gradio's broken
MediaRecorder freeze on Windows. Audio is base64-encoded in the browser
and sent as a hidden textbox value — zero Gradio audio component involved.
"""

import gradio as gr
import base64
import tempfile
import os

from stt import transcribe_audio
from tts_engine import speak_text, get_backend_name
from scoring import score_pronunciation, format_mistakes_display
from utils import get_random_sentence, get_all_difficulties, get_available_accents, SessionStats

DIFFICULTY_CHOICES = get_all_difficulties()
ACCENT_CHOICES     = get_available_accents()

# ---------------------------------------------------------------------------
# Custom recorder HTML — fully self-contained, no Gradio Audio component
# ---------------------------------------------------------------------------
RECORDER_HTML = """
<div id="sb-recorder" style="
    background:#12151c;
    border:1px solid #2a3347;
    border-radius:14px;
    padding:24px 20px;
    font-family:'Inter',sans-serif;
    color:#e8ecf4;
">

  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
    <div id="sb-dot" style="
        width:12px;height:12px;border-radius:50%;
        background:#4a5568;
        transition:background 0.3s,box-shadow 0.3s;
    "></div>
    <span id="sb-status" style="font-size:14px;color:#8892a4;">Ready to record</span>
  </div>

  <div style="display:flex;gap:10px;flex-wrap:wrap;">
    <button id="sb-start" onclick="sbStart()" style="
        background:linear-gradient(135deg,#00e5ff,#0090b8);
        color:#000;font-weight:700;font-size:14px;
        border:none;border-radius:8px;
        padding:10px 22px;cursor:pointer;
        box-shadow:0 4px 20px rgba(0,229,255,0.3);
    ">🎙️ Start Recording</button>

    <button id="sb-stop" onclick="sbStop()" disabled style="
        background:#1a1e28;color:#4a5568;font-weight:600;font-size:14px;
        border:1px solid #2a3347;border-radius:8px;
        padding:10px 22px;cursor:not-allowed;
        transition:all 0.2s;
    ">⏹ Stop</button>

    <button id="sb-clear" onclick="sbClear()" style="
        background:#1a1e28;color:#8892a4;font-weight:600;font-size:14px;
        border:1px solid #2a3347;border-radius:8px;
        padding:10px 22px;cursor:pointer;
    ">🗑 Clear</button>
  </div>

  <div id="sb-timer" style="
      margin-top:14px;font-family:'DM Mono',monospace;
      font-size:13px;color:#4a5568;display:none;
  ">00:00</div>

  <audio id="sb-preview" controls style="
      margin-top:16px;width:100%;display:none;
      border-radius:8px;
  "></audio>

  <div id="sb-ready-msg" style="
      margin-top:12px;font-size:13px;color:#00ff88;display:none;
  ">✅ Recording ready — click <strong>Analyse</strong> below</div>

</div>

<script>
(function(){
  let mediaRecorder = null;
  let chunks        = [];
  let timerInterval = null;
  let seconds       = 0;

  function setStatus(text, color){
    document.getElementById('sb-status').textContent = text;
    document.getElementById('sb-dot').style.background = color;
    document.getElementById('sb-dot').style.boxShadow =
        color === '#ff4757' ? '0 0 8px #ff4757' : 'none';
  }

  function fmtTime(s){
    return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
  }

  window.sbStart = async function(){
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      chunks = [];

      // Prefer wav-compatible mime; fallback to webm
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                   ? 'audio/webm;codecs=opus' : 'audio/webm';

      mediaRecorder = new MediaRecorder(stream, {mimeType: mime});

      mediaRecorder.ondataavailable = e => { if(e.data.size > 0) chunks.push(e.data); };

      mediaRecorder.onstop = () => {
        // Stop all tracks immediately so mic light goes off
        stream.getTracks().forEach(t => t.stop());

        const blob = new Blob(chunks, {type: mediaRecorder.mimeType});
        const url  = URL.createObjectURL(blob);

        // Show preview player
        const preview = document.getElementById('sb-preview');
        preview.src   = url;
        preview.style.display = 'block';

        document.getElementById('sb-ready-msg').style.display = 'block';

        // Convert to base64 and push into hidden Gradio textbox
        const reader = new FileReader();
        reader.onloadend = () => {
          const b64 = reader.result.split(',')[1];
          // Find the hidden textarea Gradio rendered for audio_b64
          const textareas = document.querySelectorAll('textarea');
          for(const ta of textareas){
            if(ta.closest('#audio-b64-box')){
              const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                  window.HTMLTextAreaElement.prototype, 'value').set;
              nativeInputValueSetter.call(ta, b64);
              ta.dispatchEvent(new Event('input', {bubbles:true}));
              break;
            }
          }
        };
        reader.readAsDataURL(blob);

        setStatus('Recording ready', '#00ff88');
        clearInterval(timerInterval);
        document.getElementById('sb-timer').style.display = 'none';
        document.getElementById('sb-start').disabled = false;
        document.getElementById('sb-stop').disabled  = true;
        document.getElementById('sb-stop').style.cursor = 'not-allowed';
        document.getElementById('sb-stop').style.color  = '#4a5568';
      };

      mediaRecorder.start(100); // collect in 100ms chunks

      // UI updates
      setStatus('Recording…', '#ff4757');
      document.getElementById('sb-start').disabled = true;
      document.getElementById('sb-stop').disabled  = false;
      document.getElementById('sb-stop').style.cursor  = 'pointer';
      document.getElementById('sb-stop').style.color   = '#e8ecf4';
      document.getElementById('sb-stop').style.background = '#1a1e28';
      document.getElementById('sb-preview').style.display = 'none';
      document.getElementById('sb-ready-msg').style.display = 'none';

      seconds = 0;
      document.getElementById('sb-timer').style.display = 'block';
      document.getElementById('sb-timer').textContent = '00:00';
      timerInterval = setInterval(()=>{
        seconds++;
        document.getElementById('sb-timer').textContent = fmtTime(seconds);
        if(seconds >= 60) window.sbStop(); // auto-stop at 60s
      }, 1000);

    } catch(err) {
      setStatus('Mic error: ' + err.message, '#ff4757');
    }
  };

  window.sbStop = function(){
    if(mediaRecorder && mediaRecorder.state !== 'inactive'){
      mediaRecorder.stop();
    }
  };

  window.sbClear = function(){
    chunks = [];
    const preview = document.getElementById('sb-preview');
    preview.src   = '';
    preview.style.display = 'none';
    document.getElementById('sb-ready-msg').style.display = 'none';
    setStatus('Ready to record', '#4a5568');
    // Clear the hidden textbox
    const textareas = document.querySelectorAll('textarea');
    for(const ta of textareas){
      if(ta.closest('#audio-b64-box')){
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype,'value').set;
        setter.call(ta, '');
        ta.dispatchEvent(new Event('input',{bubbles:true}));
        break;
      }
    }
  };
})();
</script>
"""

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

:root {
    --bg-primary:#0a0c10; --bg-card:#12151c; --bg-elevated:#1a1e28;
    --accent-cyan:#00e5ff; --accent-green:#00ff88;
    --text-primary:#e8ecf4; --text-secondary:#8892a4; --text-muted:#4a5568;
    --border-subtle:#1e2535; --border-accent:#2a3347;
    --radius-sm:8px; --radius-md:14px; --radius-lg:20px;
    --glow-cyan:0 0 30px rgba(0,229,255,0.15);
    --transition:all 0.2s cubic-bezier(0.4,0,0.2,1);
}

.gradio-container {
    background:var(--bg-primary) !important;
    font-family:'Inter',sans-serif !important;
    max-width:1200px !important; margin:0 auto !important;
}
body { background:var(--bg-primary) !important; }

#app-header {
    background:linear-gradient(135deg,#0d1117 0%,#12151c 40%,#0a1628 100%);
    border:1px solid var(--border-accent); border-radius:var(--radius-lg);
    padding:36px 40px; margin-bottom:24px; position:relative; overflow:hidden;
}
#app-header::before {
    content:''; position:absolute; top:0;left:0;right:0; height:2px;
    background:linear-gradient(90deg,transparent,var(--accent-cyan),var(--accent-green),transparent);
}

textarea, input[type="text"] {
    background:var(--bg-elevated) !important;
    border:1px solid var(--border-accent) !important;
    border-radius:var(--radius-sm) !important;
    color:var(--text-primary) !important;
    font-family:'Inter',sans-serif !important; font-size:15px !important;
}
textarea:focus, input:focus {
    border-color:var(--accent-cyan) !important;
    box-shadow:var(--glow-cyan) !important; outline:none !important;
}

label, .label-wrap {
    color:var(--text-secondary) !important;
    font-family:'DM Mono',monospace !important;
    font-size:11px !important; letter-spacing:0.08em !important;
    text-transform:uppercase !important; font-weight:500 !important;
}

button.primary {
    background:linear-gradient(135deg,var(--accent-cyan),#0090b8) !important;
    color:#000 !important; font-family:'Syne',sans-serif !important;
    font-weight:700 !important; border:none !important;
    border-radius:var(--radius-sm) !important;
    box-shadow:0 4px 20px rgba(0,229,255,0.3) !important;
}
button.secondary {
    background:var(--bg-elevated) !important;
    color:var(--text-secondary) !important;
    border:1px solid var(--border-accent) !important;
    border-radius:var(--radius-sm) !important;
}

#score-display textarea {
    font-family:'Syne',sans-serif !important; font-size:48px !important;
    font-weight:800 !important; text-align:center !important;
    color:var(--accent-cyan) !important; border:none !important;
    background:transparent !important;
}
#transcript-output textarea {
    font-family:'DM Mono',monospace !important; font-size:14px !important;
    color:var(--accent-green) !important;
    border-color:rgba(0,255,136,0.2) !important;
    background:rgba(0,255,136,0.03) !important;
}
#feedback-output textarea {
    font-family:'Syne',sans-serif !important; font-size:17px !important;
    font-weight:600 !important; color:var(--text-primary) !important;
}
#audio-b64-box { display:none !important; }

.gr-markdown h1 {
    font-family:'Syne',sans-serif !important; font-size:36px !important;
    font-weight:800 !important; color:var(--text-primary) !important;
    letter-spacing:-1px !important;
}
.gr-markdown p { color:var(--text-secondary) !important; font-size:14px !important; }
.gr-markdown code {
    font-family:'DM Mono',monospace !important;
    background:var(--bg-elevated) !important;
    color:var(--accent-cyan) !important;
    padding:2px 6px !important; border-radius:4px !important;
}

::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:var(--bg-primary); }
::-webkit-scrollbar-thumb { background:var(--border-accent); border-radius:3px; }
"""

# ---------------------------------------------------------------------------
# Backend: decode base64 audio → temp file → Whisper
# ---------------------------------------------------------------------------

def run_analysis(audio_b64: str, target_sentence: str, session_stats: dict):
    stats = SessionStats(**session_stats) if session_stats else SessionStats()

    if not audio_b64 or not audio_b64.strip():
        return (
            "⚠️ No recording found. Record audio first, then click Analyse.",
            "—", "_Record audio first._", "—",
            None, stats.__dict__, stats.format_history_md(),
        )

    # Decode base64 → temp file
    try:
        audio_bytes = base64.b64decode(audio_b64)
        suffix = ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
    except Exception as e:
        return (
            f"Audio decode error: {e}", "0 / 100",
            "❌ Could not decode audio.", "Try again.",
            None, stats.__dict__, stats.format_history_md(),
        )

    # Transcribe
    try:
        transcript = transcribe_audio(tmp_path)
    except Exception as e:
        transcript = ""
        print(f"[STT] Error: {e}")
    finally:
        try: os.remove(tmp_path)
        except: pass

    if not transcript or not transcript.strip():
        return (
            "_No speech detected._", "0 / 100",
            "❌ No speech detected.", "Speak closer to the mic.",
            None, stats.__dict__, stats.format_history_md(),
        )

    result       = score_pronunciation(target_sentence, transcript)
    score_str    = f"{result.score} / 100  {result.grade}"
    mistakes_md  = format_mistakes_display(result)
    feedback_str = (
        f"{result.feedback_summary}\n\n"
        f"Similarity: {result.similarity_pct:.1f}%  •  "
        f"Words spoken: {result.word_count_spoken}/{result.word_count_target}"
    )
    tts_path = speak_text(target_sentence)

    stats.record_attempt(target_sentence, transcript, result.score, result.grade)

    return (
        transcript, score_str, mistakes_md, feedback_str,
        tts_path, stats.__dict__, stats.format_history_md(),
    )


def load_random_sentence(difficulty: str) -> str:
    sentence, _ = get_random_sentence(difficulty)
    return sentence


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    tts_backend = get_backend_name()

    with gr.Blocks(
        css=CUSTOM_CSS,
        title="SpeakBetter AI",
        theme=gr.themes.Base(primary_hue="cyan", neutral_hue="slate"),
    ) as app:

        gr.Markdown("""
# SpeakBetter AI
### Real-Time Pronunciation & Voice Feedback Coach

Powered by **faster-whisper** · **Coqui TTS** · **Python**

---
""", elem_id="app-header")

        session_state = gr.State(value=SessionStats().__dict__)

        with gr.Row(equal_height=False):

            # ---- LEFT --------------------------------------------------------
            with gr.Column(scale=1, min_width=320):

                gr.Markdown("### 🎯 Practice Setup")

                with gr.Group():
                    difficulty_dropdown = gr.Dropdown(
                        label="Difficulty", choices=DIFFICULTY_CHOICES,
                        value="all", interactive=True,
                    )
                    random_btn = gr.Button("🎲  Random Sentence", variant="secondary", size="sm")

                target_sentence = gr.Textbox(
                    label="Target Sentence — Read this aloud",
                    value="The quick brown fox jumps over the lazy dog.",
                    lines=3, interactive=True,
                )

                gr.Markdown("### 🎙️ Record Your Voice")

                # Custom JS recorder — no Gradio Audio component = no freeze
                gr.HTML(RECORDER_HTML)

                # Hidden textbox receives base64 audio from JS
                audio_b64 = gr.Textbox(
                    visible=True,
                    label="audio_b64 (hidden)",
                    elem_id="audio-b64-box",
                    lines=1,
                )

                with gr.Row():
                    submit_btn = gr.Button("⚡  Analyse Pronunciation", variant="primary", scale=2)
                    retry_btn  = gr.Button("🔁  New Sentence", variant="secondary", scale=1)

                gr.Markdown("### 🌐 Accent Mode _(beta)_")
                accent_dropdown = gr.Dropdown(
                    label="Target Accent", choices=ACCENT_CHOICES,
                    value="General American", interactive=True,
                )
                gr.Markdown(f"<small>TTS: `{tts_backend}`</small>")

            # ---- RIGHT -------------------------------------------------------
            with gr.Column(scale=1, min_width=360):

                gr.Markdown("### 📊 Analysis Results")

                transcript_output = gr.Textbox(
                    label="What Whisper Heard", lines=3,
                    interactive=False, elem_id="transcript-output",
                    placeholder="Transcribed speech appears here...",
                )
                score_output = gr.Textbox(
                    label="Pronunciation Score", interactive=False,
                    elem_id="score-display", placeholder="— / 100",
                )
                feedback_output = gr.Textbox(
                    label="Feedback", lines=3, interactive=False,
                    elem_id="feedback-output",
                    placeholder="Coaching feedback appears here...",
                )
                mistakes_output = gr.Markdown(
                    value="_Submit a recording to see analysis._",
                )

                gr.Markdown("### 🔊 Correct Pronunciation Playback")
                tts_output = gr.Audio(
                    label="Correct pronunciation", interactive=False, autoplay=False,
                )

        with gr.Accordion("📈 Session History", open=False):
            history_output = gr.Markdown(value="_No attempts yet._")

        with gr.Accordion("ℹ️ How to Use", open=False):
            gr.Markdown("""
1. Pick difficulty → **Random Sentence**
2. Click **🎙️ Start Recording** → speak → click **⏹ Stop**
3. Click **⚡ Analyse Pronunciation**
4. Review score, mistakes, and listen to correct playback
""")

        # ---- Events ----------------------------------------------------------
        submit_btn.click(
            fn=run_analysis,
            inputs=[audio_b64, target_sentence, session_state],
            outputs=[
                transcript_output, score_output, mistakes_output,
                feedback_output, tts_output, session_state, history_output,
            ],
        )

        retry_btn.click(fn=load_random_sentence, inputs=[difficulty_dropdown], outputs=[target_sentence])
        random_btn.click(fn=load_random_sentence, inputs=[difficulty_dropdown], outputs=[target_sentence])

    return app


if __name__ == "__main__":
    app = build_ui()
    app.queue(max_size=5)
    app.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
