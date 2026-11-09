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

**A Windows voice assistant with a transparent glowing 3D HUD, local speech recognition and reasoning, network-dependent neural speech, hardware automation, and barge-in controls.**

</div>

---

## 🌟 Overview

**Rudra** is a Windows desktop companion built with an **Electron + React 18 HUD** and a local **FastAPI** backend. Speech recognition uses local **faster-whisper** models and responses use a separately installed local **Ollama** runtime. Speech synthesis prefers Microsoft's online Edge TTS service and falls back to local `pyttsx3`; Rudra is therefore not fully offline.

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
│  • LLM: Streaming Ollama queue -> regex sentence boundary splitter     │
│  • TTS: Microsoft Edge TTS (online; reply text sent) + local fallback │
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
  - **English:** `en-US-SteffanNeural`
  - **Hindi (Devanagari):** `hi-IN-MadhurNeural`
  - **Punjabi (Gurmukhi):** `pa-IN-GurpreetNeural`
- **🎤 Instant microphone mute:** The HUD mute control disables microphone capture and clears buffered audio; typed requests remain available while muted.
- **🧠 Hardware-aware Ollama selection:** The settings menu lists installed Ollama models and recommends Low, Mid, or High profiles based on system RAM. GPU VRAM is not currently inspected.
- **🎬 Autonomous Media Control:** Playwright browser automation with persistent context (`.rudra/browser/`) searches and auto-plays songs/videos on YouTube without repetitive sign-ins.
- **🖥️ Desktop & Hardware Automation:** Control master system volume, screen brightness, take timestamped screenshots to `~/Pictures/Rudra/`, and lock your Windows workstation.
- **📂 Scoped File Access:** Search, open, and read files only inside Desktop, Documents, Downloads, Pictures, Music, or Videos. App closing requires confirmation.
- **📄 Document Workspace:** Summarize TXT, Markdown, PDF, DOCX, and PPTX files with the on-demand local document model; follow progress, manage and regenerate seven styles of notes, and export Markdown, text, Word, PDF, or flashcard JSON.

Uploaded file copies are removed after text extraction. Extracted source text is
kept in the local notes database so saved notes can be regenerated in another
style.

## 🔐 Privacy and Data Flow

- Speech recognition runs with the local faster-whisper model. LLM requests are
  sent to the local Ollama service (loopback by default); Ollama and its model
  weights are separate prerequisites and are not bundled with Rudra.
- Neural speech uses Microsoft's online Edge TTS service when available. The
  text being spoken is sent to that service. If it is unavailable, Rudra uses
  local `pyttsx3` speech when a usable system voice is installed; voice quality
  and language support may differ.
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

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS:** Windows 10 or 11 (64-bit)
- **Node.js:** v20+ LTS
- **Python:** v3.10 to v3.12
- **Ollama:** [Download & install Ollama](https://ollama.com); it must be
  installed separately and running for LLM replies and document notes.

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
