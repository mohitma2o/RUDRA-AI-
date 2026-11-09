# RUDRA AI — App-like Voice Assistant for Windows

<div align="center">

![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Node.js](https://img.shields.io/badge/Node.js-20%2B-green?logo=node.js)
![Electron](https://img.shields.io/badge/Electron-33-47848F?logo=electron)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v4-38B2AC?logo=tailwindcss)
![Ollama](https://img.shields.io/badge/LLM-Ollama%20(Qwen%202.5)-black?logo=ollama)
![License](https://img.shields.io/badge/License-MIT-purple)

**A Windows voice assistant with a futuristic cyan ARC HUD, local speech recognition and reasoning, network-dependent neural speech, desktop automation, and live system telemetry.**

</div>

---

## 🌟 Overview

**Rudra** is a Windows desktop companion built with an **Electron + React 18 HUD** and a local **FastAPI** backend. Speech recognition uses local **faster-whisper** models. New installs default to **Gemini 2.5 Flash** Cloud mode to avoid warming a local LLM at launch; the saved engine choice is respected on later launches. Select either Gemini Cloud or a separately installed local **Ollama** runtime. Cloud failures are surfaced without silently switching providers; three consecutive Gemini failures open a 30-second circuit breaker. Switching to Local checks Ollama within three seconds and leaves the current mode unchanged if it is unavailable. Speech synthesis prefers Microsoft's online Edge TTS service and falls back to local **Kokoro-82M** for English and Hindi, then Windows/system voices (including Punjabi where installed). Edge TTS is online, so Rudra is not fully offline.

Say **"Rudra"** (or press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Space</kbd>) to activate. Rudra captures audio with browser Web Audio echo cancellation, transcribes locally, executes desktop tasks, or streams responses with multilingual text-to-speech.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ELECTRON RENDERER (HUD)                         │
│  • React 18 + Tailwind v4 + Zustand                                    │
│  • Web Audio API: Echo Cancellation, RMS VAD (450ms tail-silence)      │
│  • Glowing 3D Orb Visualizer (Idle / Listening / Thinking / Speaking)  │
│  • Instant Barge-in: Speaking or clicking immediately stops playback   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ WebSocket (/ws/voice)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND (Python)                       │
│  • STT: faster-whisper (in-memory 16kHz Int16 PCM)                     │
│  • Wake Word: Multilingual fuzzy token matcher (rapidfuzz)             │
│  • Fast-path Router: <150ms execution for volume, brightness, time     │
│  • Tool Registry: Tier.AUTO vs Tier.CONFIRM security gate             │
│  • LLM: selected Gemini Cloud or streaming local Ollama                 │
│  • TTS: Edge Neural online -> Kokoro local -> system voice fallback    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
┌─────────────────────┐                           ┌─────────────────────┐
│  HARDWARE & SYSTEM  │                           │ BROWSER AUTOMATION  │
│ • pycaw (Volume)    │                           │ • Playwright        │
│ • Screen Brightness │                           │ • YouTube Autoplay  │
│ • Lock / Screenshot │                           │ • Web Navigation    │
│ • Sleep / Shutdown  │                           │ • Persistent Profile│
└─────────────────────┘                           └─────────────────────┘
```

---

## ⚡ Expected Voice Latency (Indicative)

These are rough planning estimates for entry-level hardware (for example,
**Intel i3 10th Gen, 12 GB RAM**) with a warm local model, not benchmark
results or guarantees. Cold model startup, device load, language, and the
network-dependent Edge TTS request can make actual latency longer.

| Pipeline stage | Approximate latency |
|---|---|
| **VAD endpointing** | About 450 ms tail silence |
| **Wake word and speech recognition** | 600–1,100 ms |
| **Fast-path hardware actions** | 40–180 ms |
| **Warm Ollama model to first sentence** | 800–1,800 ms |
| **Edge TTS first audio chunk** | 250–600 ms when the service responds promptly |
| **Total time to first word** | **About 2,100–4,000 ms** |

Rudra sends timing events for individual voice turns so actual device behavior
can be measured locally; the estimates above have not been independently
benchmarked across supported hardware.

---

## ✨ Key Capabilities

- **🎙️ Advanced Audio Pipeline:** Echo cancellation and RMS Voice Activity Detection running directly in the browser process ensure Rudra doesn't trigger on its own speakers.
- **⚡ Instant Barge-in Interruption:** Start speaking or click the 3D Orb while Rudra is speaking to immediately halt playback and begin a new query.
- **🛡️ Two-Tier Safety System (`Tier.AUTO` vs `Tier.CONFIRM`):**
  - `Tier.AUTO`: Non-destructive queries (time, volume, brightness, screenshots) run immediately.
  - `Tier.CONFIRM`: Destructive commands (power off, restart, sleep) pause and show the requested tool and parameters in the HUD. The user must choose **Approve** or **Cancel**; the prompt expires after 20 seconds. Voice-only approval is not supported.
- **🌐 Multilingual by Design:** Automatic script detection responds with native accents and neural voices:
  - **English:** `en-IN-NeerjaNeural`
  - **Hindi (Devanagari):** `hi-IN-SwaraNeural`
  - **Punjabi (Gurmukhi):** `pa-IN-GurpreetNeural`
- **🪪 Creator identity:** English, Hindi/Hinglish, and Punjabi questions about
  who created Rudra receive a deterministic response crediting Mohit Mattoo,
  before either the cloud or local language model is called.
- **☁️ Optional Gemini replies:** Configure a key in Settings or provide
  `GEMINI_API_KEY` in the repository-root `.env` file. New installs start in
  Gemini Cloud mode; a previously saved engine choice is retained. Gemini is
  used for assistant replies only when Cloud mode is selected; Cloud errors are shown
  and spoken without silently switching to Ollama. After three consecutive
  Gemini failures, requests pause for 30 seconds before a retry. Switch modes
  from the HUD header or by saying “switch to cloud mode” / “switch to local
  mode.”
- **🗣️ Speech interruption:** Speak while Rudra is talking to stop playback
  and submit your interruption; the renderer's existing VAD handles barge-in
  without opening a second microphone listener.
- **🎤 Instant microphone mute:** The HUD mute control disables microphone capture and clears buffered audio; typed requests remain available while muted.
- **🧠 Hardware-aware Ollama selection:** The settings menu lists installed Ollama models and recommends Low, Mid, or High profiles based on system RAM. GPU VRAM is not currently inspected.
- **🎬 Autonomous Media Control:** Playwright browser automation with persistent context (`.rudra/browser/`) searches and auto-plays songs/videos on YouTube without repetitive sign-ins.
- **🖥️ Deterministic Desktop Controls:** Exact voice intents route app launches, camera capture, volume, brightness, screenshots, and lock-screen requests directly to their registered tools instead of asking the language model to claim it performed them.
- **👁️ Clipboard & Screen Assistance:** Explicitly request a clipboard summary or screen explanation. Clipboard/screen content is sent only to local Ollama; screen analysis requires an installed Ollama vision model such as `qwen2.5vl:3b`.
- **📊 Live HUD Telemetry:** The cyan ARC interface displays live CPU/RAM use and the active Ollama model.
- **📜 Vichar of the Day:** A daily Bhagavad Gita verse with a short, labeled practical paraphrase.
- **📂 Scoped File Access:** Search, open, and read files only inside Desktop, Documents, Downloads, Pictures, Music, or Videos. App closing requires confirmation.
- **📄 Document Workspace:** Summarize TXT, Markdown, PDF, DOCX, and PPTX files with the on-demand local document model; follow progress, manage and regenerate seven styles of notes, and export Markdown, text, Word, PDF, or flashcard JSON.

Uploaded file copies are removed after text extraction. Extracted source text is
kept in the local notes database so saved notes can be regenerated in another
style.

## 🔐 Privacy and Data Flow

- Speech recognition runs with the local faster-whisper model. In Cloud mode,
  assistant conversation text and recent conversation history are sent to
  Google's Gemini API. A Cloud request failure does not switch providers;
  switch to Local mode explicitly to use Ollama (loopback by default).
  New installs default to Cloud mode; an explicitly saved engine choice is
  retained on later starts. Ollama is not warmed while Cloud mode is active,
  and selecting Local checks its API within three seconds.
  Keys entered in Settings are stored in Rudra's per-user config under
  `%APPDATA%\Rudra AI`; they are not returned to the HUD or written to the
  repository.
- Document text, clipboard content, and screen images continue to use local
  Ollama. Ollama and its model weights are separate prerequisites and are not
  bundled with Rudra.
- Neural speech uses Microsoft's online Edge TTS service when available. The
  text being spoken is sent to that service. If it is unavailable, Rudra uses
  the local Kokoro-82M model for English and Hindi when its model files are
  available, then `pyttsx3` and an installed system voice. Kokoro weights may
  need to download the first time and are cached locally. Kokoro does not
  currently provide Punjabi voices, so offline Punjabi speech depends on an
  installed Punjabi system voice and may not be available on every device.
- Document text is summarized by local Ollama. The temporary uploaded file is
  removed after extraction, but extracted source text is retained in the local
  notes database for regeneration. By default, Windows runtime data is stored
  under `%APPDATA%\Rudra AI`; deleting a note removes its saved source text.
- Browser automation and model downloads require network access when used.

---

## 🗣️ Voice Commands Cheatsheet

| Category | Example Phrases | Action / Tool |
|---|---|---|
| **System Info** | *"What time is it?"*, *"Tell me today's date"* | `get_time` (< 50ms) |
| **Diagnostics** | *"System status"*, *"Check battery level"*, *"CPU usage"* | `system_status` (< 100ms) |
| **Volume** | *"Set volume to 60"*, *"Mute audio"*, *"Volume up"* | `volume_set`, `volume_mute` |
| **Brightness** | *"Increase brightness"*, *"Set brightness to 80"*, *"Dim screen"* | `brightness_set`, `brightness_up` |
| **Media** | *"Play Shiva Tandav on YouTube"*, *"Pause music"*, *"Next track"* | `play_youtube`, `media_control` |
| **Security** | *"Lock my screen"*, *"Take a screenshot"* | `lock_screen`, `screenshot` |
| **Files** | *"Search file budget"*, *"Open file my report"*, *"Read document notes"* | `search_file`, `open_file`, `read_document` |
| **Documents** | *"Summarize document my report"* | `summarize_document` |
| **Folders / Apps** | *"Open my Documents folder"*, *"Open app Notepad"*, *"Close app Notepad"* | `open_folder`, `open_application`; closing requires confirmation |
| **Power (Safety Gate)**| *"Shutdown computer"*, *"Restart the PC"*, *"Sleep computer"* | Requires Approval (`Tier.CONFIRM`) |
| **Power Abort** | *"Cancel shutdown"*, *"Abort restart"* | `cancel_shutdown` |
| **LLM Engine** | *"Switch to cloud mode"*, *"Switch to local mode"* | Gemini 2.5 Flash / local Ollama |

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS:** Windows 10 or 11 (64-bit)
- **Node.js:** v20+ LTS
- **Python:** v3.10 to v3.12
- **Ollama:** [Download & install Ollama](https://ollama.com); it must be
  installed separately and running for local fallback replies, document notes,
  clipboard summaries, and screen analysis.
- **Optional Gemini API key:** Put `GEMINI_API_KEY=...` in the repository-root
  `.env` file or enter it in the HUD's Settings. Voice replies use Gemini when
  Cloud mode is selected; request failures are surfaced instead of falling back
  to Ollama. Choose Cloud or Local in the HUD header or use the voice commands
  above. Cloud replies send conversation text to Google.

The default voice model is `qwen2.5:1.5b`. The document model is
`qwen2.5:3b-instruct-q4_K_M` (optional, about 2 GB). You can download the
configured models from Rudra's setup notice or pull them manually:
```bash
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b-instruct-q4_K_M
```

The voice assistant uses `ollama_voice_model` from `rudra/config.json`. The
separate `ollama_doc_model` is only needed for document notes. Ollama itself
and model weights are not included in the Rudra installer.

To enable screen understanding, also install a local vision model:
```powershell
ollama pull qwen2.5vl:3b
```
Rudra selects an installed Ollama vision model automatically. Without one,
screen analysis reports that setup requirement; ordinary chat continues using
the selected voice model.

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/mohitma2o/RUDRA-AI-.git
cd RUDRA-AI-

# Install Python backend dependencies
pip install -r backend/requirements.txt

# Install Node & Frontend dependencies
npm install
npm --prefix frontend install
```

### 3. Launching in Development Mode
```bash
npm run dev
```
*This starts Vite and Electron. Electron reserves a loopback port, starts the FastAPI backend with a per-launch token, and restarts it if it exits.*

Say **“Open Notepad”**, **“Set volume to 50%”**, **“Lock PC”**, or
**“Take a screenshot”** for direct desktop actions. **“Take a photo”** captures
a webcam image in `Pictures\Rudra`; camera access depends on Windows privacy
settings. **“Summarize copied text”** summarizes clipboard text and
**“Explain what’s on my screen”** analyzes the current display. The screen and
clipboard content are processed by local Ollama; vision requires the optional
vision model above. Use the HUD microphone button to pause audio capture.

### 4. Production Build & Execution
```bash
# Compiles frontend with Vite and Electron with TypeScript
npm run build

# Launch the compiled desktop assistant
npm start
```

### Local API security and logs

The backend binds to `127.0.0.1`. HTTP API requests require the per-launch token;
the voice WebSocket authenticates its first frame and accepts only the local
development origin or Electron's `file://` origin (`null`). CORS is restricted
to those app origins, including the PATCH and DELETE methods used by document
notes.

Electron writes backend output under its user-data `logs` directory. The active
`backend.log` is capped at 5 MiB, with up to three rotated backups.

---

## ⌨️ Shortcuts & Controls

- **<kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Space</kbd>:** Global hotkey to show or hide the HUD anywhere on Windows.
- **Left-Click Orb:** Interrupts active speech or toggles speech recognition.
- **System Tray:** Right-click the Rudra icon in the Windows taskbar tray to Show, Hide, or Quit.

---

## 🧪 Automated Testing

```bash
python -m pytest tests -q
npm run test:electron
npm run build
```

The Python suite covers voice behavior, local API authentication, file-tool
allowlisting, document processing, and persistence. The Electron logger tests
verify bounded rotation and retention. The build checks the frontend and
desktop TypeScript.

---

## 📁 Repository Layout

```
RUDRA-AI-/
├── electron/               # Electron shell process
│   ├── main.ts             # Window lifecycle, tray, global shortcuts, backend spawn
│   ├── preload.ts          # Secure IPC contextBridge
│   └── tsconfig.json
├── frontend/               # React 18 UI
│   ├── src/
│   │   ├── components/     # HUD, document workspace, transcript, metrics, and setup UI
│   │   ├── hooks/          # useVoicePipeline (Web Audio VAD, barge-in, WebSocket)
│   │   ├── store/          # Zustand voice store
│   │   └── App.tsx
│   ├── index.html
│   └── vite.config.ts      # Tailwind CSS v4 + Vite plugin
├── backend/                # FastAPI Streaming Voice Backend
│   └── app/
│       ├── main.py         # Authenticated HTTP/WebSocket routes and voice pipeline
│       ├── documents/      # Document extraction, jobs, notes, and exports
│       ├── voice/          # faster-whisper STT, rapidfuzz wake, streaming LLM & TTS
│       └── tools/          # Tool registry, safety tiers, hardware & browser tools
├── rudra/                  # Core assets & models
│   ├── models/rudra.onnx   # Trained wake-word model (tracked in git)
│   ├── skills/             # Vision, system, file, and OCR skills
│   └── config.json         # Runtime config
└── tests/                  # Python and Electron automated test suites
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
