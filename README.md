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

**A high-performance, local voice assistant with a transparent glowing 3D HUD, real-time VAD, streaming speech synthesis, hardware automation, and instant barge-in.**

</div>

---

## 🌟 Overview

**Rudra** is an on-device, Jarvis-like desktop companion built for Windows. It combines the visual fluidity of an **Electron + React 18 HUD** with the low-latency power of a local **FastAPI** backend streaming **Ollama (Qwen 2.5)** and **faster-whisper**.

Say **"Rudra"** (or press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Space</kbd>) to activate. Rudra listens via browser Web Audio echo cancellation, transcribes locally, executes desktop tasks or streams responses word-by-word with natural multilingual text-to-speech.

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
│  • TTS: edge-tts (IN-Prabhat, Madhur, Gagan) + pyttsx3 offline fallback│
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

## ⚡ Performance & Latency Benchmarks (WP7)

Optimized specifically for budget hardware targets (e.g., **Intel i3 10th Gen, 12 GB RAM**):

| Pipeline Stage | Baseline (Sequential) | Rudra v2.0 (Streaming) | Speedup |
|---|---|---|---|
| **Audio VAD Endpointing** | 1,500 ms (fixed pause) | 450 ms (Web Audio RMS VAD) | **3.3x faster** |
| **Wake Word & STT** | 1,500 ms (disk I/O) | 600–1,100 ms (direct PCM memory) | **1.8x faster** |
| **Fast-path Hardware Actions** | 6,000–10,000 ms (via LLM) | 40–180 ms (regex bypass) | **30x–50x faster** |
| **LLM to First Sentence** | 3,000–8,000 ms (blocking) | 800–1,800 ms (streaming queue) | **4x faster** |
| **TTS First Audio Chunk** | 1,200–2,500 ms (full turn) | 250–600 ms (first sentence only) | **4x faster** |
| **Total Time to First Word** | **~7,000–13,000 ms** | **~2,100–3,800 ms** | **~3.5x faster overall** |

---

## ✨ Key Capabilities

- **🎙️ Advanced Audio Pipeline:** Echo cancellation and RMS Voice Activity Detection running directly in the browser process ensure Rudra doesn't trigger on its own speakers.
- **⚡ Instant Barge-in Interruption:** Start speaking or click the 3D Orb while Rudra is speaking to immediately halt playback and begin a new query.
- **🛡️ Two-Tier Safety System (`Tier.AUTO` vs `Tier.CONFIRM`):**
  - `Tier.AUTO`: Non-destructive queries (time, volume, brightness, screenshots) run immediately.
  - `Tier.CONFIRM`: Destructive commands (power off, restart, sleep) pause and require user confirmation via voice or interactive HUD buttons.
- **🌐 Multilingual by Design:** Automatic script detection responds with native accents and neural voices:
  - **English (India):** `en-IN-PrabhatNeural`
  - **Hindi (Devanagari):** `hi-IN-MadhurNeural`
  - **Punjabi (Gurmukhi):** `pa-IN-GaganNeural`
- **🎬 Autonomous Media Control:** Playwright browser automation with persistent context (`.rudra/browser/`) searches and auto-plays songs/videos on YouTube without repetitive sign-ins.
- **🖥️ Desktop & Hardware Automation:** Control master system volume, screen brightness, take timestamped screenshots to `~/Pictures/Rudra/`, and lock your Windows workstation.

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
| **Power (Safety Gate)**| *"Shutdown computer"*, *"Restart the PC"*, *"Sleep computer"* | Requires Approval (`Tier.CONFIRM`) |
| **Power Abort** | *"Cancel shutdown"*, *"Abort restart"* | `cancel_shutdown` |

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS:** Windows 10 or 11 (64-bit)
- **Node.js:** v20+ LTS
- **Python:** v3.10 to v3.12
- **Ollama:** [Download & install Ollama](https://ollama.com)

Pull the recommended lightweight voice model:
```bash
ollama pull qwen2.5:1.5b
```
*(For higher accuracy on machines with 16GB+ RAM, use `ollama pull qwen2.5:3b-instruct-q4_K_M`)*

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
*This concurrently starts the FastAPI server (`http://127.0.0.1:8000`), the Vite dev server (`http://localhost:5173`), and launches the Electron HUD.*

### 4. Production Build & Execution
```bash
# Compiles frontend with Vite and Electron with TypeScript
npm run build

# Launch the compiled desktop assistant
npm start
```

---

## ⌨️ Shortcuts & Controls

- **<kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Space</kbd>:** Global hotkey to show or hide the HUD anywhere on Windows.
- **Left-Click Orb:** Interrupts active speech or toggles speech recognition.
- **System Tray:** Right-click the Rudra icon in the Windows taskbar tray to Show, Hide, or Quit.

---

## 🧪 Automated Testing

The repository contains an automated test suite with **66 comprehensive unit tests**:

```bash
python -m pytest tests/
```

- `tests/test_wake.py`: Exact wake words, Hindi Devanagari, Punjabi Gurmukhi, fuzzy typo tolerance, and false-positive rejections.
- `tests/test_pipeline.py`: Script language detection, sentence boundaries, safety confirmation gates, and fast-path regex intent resolution.
- `tests/test_agent.py`: Tool dispatch, screen summaries, file search, and dynamic application resolution.

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
│   │   ├── components/     # Glowing Orb, Live Transcript, Metrics, SettingsModal, HUD
│   │   ├── hooks/          # useVoicePipeline (Web Audio VAD, barge-in, WebSocket)
│   │   ├── store/          # Zustand voice store
│   │   └── App.tsx
│   ├── index.html
│   └── vite.config.ts      # Tailwind CSS v4 + Vite plugin
├── backend/                # FastAPI Streaming Voice Backend
│   └── app/
│       ├── main.py         # /ws/voice WebSocket pipeline, warmup, fast-path
│       ├── voice/          # faster-whisper STT, rapidfuzz wake, streaming LLM & TTS
│       └── tools/          # Tool registry, safety tiers, hardware & browser tools
├── rudra/                  # Core assets & models
│   ├── models/rudra.onnx   # Trained wake-word model (tracked in git)
│   ├── skills/             # Vision, system, file, and OCR skills
│   └── config.json         # Runtime config
└── tests/                  # Pytest automated test suite
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
