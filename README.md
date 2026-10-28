# RUDRA AI — App-like Voice Assistant for Windows

Rudra is a modern, voice-activated desktop assistant for Windows. Powered by **Electron**, **React 18 (Vite, Tailwind v4, Zustand)**, and a local **FastAPI** backend with streaming **Ollama (Qwen 2.5)** and **faster-whisper**.

Say **"Rudra"** (or press `Ctrl+Shift+Space`) to wake it. It streams voice responses with an interactive glowing 3D Orb HUD, real-time waveform reactions, instant barge-in support, and desktop tool automation.

---

## Architecture & Work Packages (WP0 - WP9)

```
RUDRA-AI-/
├── electron/               # Electron shell (main process, tray, hotkey, transparent HUD window)
│   ├── main.ts
│   └── preload.ts
├── frontend/               # React HUD UI (Vite, Tailwind CSS v4, Zustand voice store)
│   ├── src/
│   │   ├── components/     # Orb, Transcript, Metrics, SettingsModal, HUD
│   │   ├── hooks/          # useVoicePipeline (Web Audio VAD, barge-in, WebSocket)
│   │   └── store/          # Zustand voice store
├── backend/                # FastAPI streaming voice backend
│   └── app/
│       ├── main.py         # /ws/voice WebSocket pipeline & /health endpoint
│       ├── voice/          # faster-whisper STT, rapidfuzz wake, streaming LLM & TTS
│       └── tools/          # Registry, Tier.AUTO & Tier.CONFIRM, hardware & browser tools
├── rudra/                  # Legacy system-tray voice loop & model weights
│   ├── models/rudra.onnx   # Trained wake word ONNX model (do not delete)
│   └── skills/             # System automation, vision, file search, OCR
└── tests/                  # Automated pytest suite (66 unit & pipeline tests)
```

---

## Key Features

- **Pulsing 3D Orb HUD** — Transparent, always-on-top glassmorphic overlay with dynamic reactive glows for idle, listening, thinking, speaking, and confirmation states.
- **Microphone Echo Cancellation & VAD** — Audio captured directly in the Electron window via Web Audio API with native browser echo cancellation and RMS voice activity detection (450ms tail silence).
- **Streaming LLM to Speech (< 3s to first word)** — Ollama tokens stream immediately into a sentence splitter; edge-tts synthesises sentence 1 while sentence 2 is being generated.
- **Barge-in Interruption** — Speaking over the assistant or clicking the Orb immediately terminates active TTS playback.
- **Safety Tiers & Confirmations** — Destructive actions (shutdown, restart, sleep) require explicit voice or UI button approval (`Tier.CONFIRM`).
- **Fast-path Hardware Tools** — Volume, mute, screen brightness, lock screen, and screenshots execute in < 150ms without hitting the LLM.
- **Browser & YouTube Automation** — Playwright persistent browser context automates YouTube search & playback.
- **Multilingual Support** — Native recognition and TTS in Indian English (`en-IN-PrabhatNeural`), Hindi (`hi-IN-MadhurNeural`), and Punjabi (`pa-IN-GaganNeural`).
- **Global Hotkey & Tray** — `Ctrl+Shift+Space` toggles the HUD from anywhere on Windows.

---

## Quick Start

### 1. Prerequisites
- Windows 10/11
- Python 3.10+
- Node.js 20+
- [Ollama](https://ollama.com) running locally (`ollama pull qwen2.5:1.5b` or `qwen2.5:3b-instruct-q4_K_M`)

### 2. Install Dependencies
```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Root and Frontend dependencies
npm install
npm --prefix frontend install
```

### 3. Run Development Mode
```bash
# Starts FastAPI backend (port 8000), Vite dev server (port 5173), and Electron shell
npm run dev
```

### 4. Build for Production
```bash
npm run build
npm start
```

---

## Running Automated Tests

```bash
python -m pytest tests/
```
All 66 tests verify wake word variants (Hindi/Punjabi/fuzzy typos), streaming sentence boundaries, tool confirmation security tiers, and fast-path intent resolution.

