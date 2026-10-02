# RUDRA AI — Local Voice Assistant for Windows

Rudra is a Jarvis-style voice assistant that runs silently in the Windows system tray.
Say **"Rudra"** to wake it, ask a question or give a command, and it speaks back in
Hindi, English, or Punjabi. Everything runs locally — no cloud required (except TTS,
which uses Microsoft Neural voices via edge-tts).

---

## Features

- **Custom wake word** — trained `rudra.onnx` model, always listening in the background
- **Speech-to-text** — faster-whisper (`base` model, runs locally)
- **LLM responses** — Ollama local inference; model selected by hardware (see below)
- **Text-to-speech** — edge-tts with Hindi (`hi-IN-MadhurNeural`) default
- **Desktop automation** — open/close apps, search files, take screenshots, web search
- **Scripture-grounded RAG** — ChromaDB + sentence-transformers pipeline is fully wired;
  corpus ingestion is deferred by design (data/ is currently empty, returns gracefully)
- **System tray UI** — pystray icon with Pause / Status / Quit menu
- **Packagable** — PyInstaller `build.spec` produces a standalone `dist/Rudra/Rudra.exe`

---

## Requirements

- Windows 10/11
- Python 3.10+
- [Ollama](https://ollama.com) installed and running

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/mohitma2o/RUDRA-AI-.git
cd RUDRA-AI-

# 2. Install Python dependencies
cd rudra
pip install -r requirements.txt

# 3. Pull the Ollama model
#    For 12 GB RAM machines:
ollama pull qwen2.5:3b-instruct-q4_K_M
#    For lower-RAM machines, edit config.json and use:
#    ollama pull tinyllama

# 4. (Optional) Copy .env.example to .env and add API keys
#    if you want to use OpenAI or Anthropic instead of Ollama
cp .env.example .env

# 5. Run from source
python main.py
```

A tray icon appears. Right-click → **Quit** to exit.

---

## Hardware Profiles

Edit `rudra/config.json` to match your machine:

| Machine | RAM | `ollama_model` | `ollama_threads` |
|---------|-----|----------------|-----------------|
| i3 10th Gen (primary) | 12 GB | `qwen2.5:3b-instruct-q4_K_M` | 4 |
| Low-RAM secondary | < 8 GB | `tinyllama:latest` | 2 |

---

## Project Structure

```
RUDRA-AI-/
├── CLAUDE.md               # AI assistant context file (persistent)
├── README.md
├── rudra/
│   ├── main.py             # Entry point — tray + wake loop
│   ├── agent.py            # Intent detection + tool dispatch
│   ├── llm.py              # Ollama / OpenAI / Anthropic routing
│   ├── stt.py              # faster-whisper STT
│   ├── tts.py              # edge-tts TTS
│   ├── wakeword.py         # openWakeWord listener
│   ├── config.json         # Runtime configuration
│   ├── build.spec          # PyInstaller spec
│   ├── models/
│   │   └── rudra.onnx      # Trained wake-word model (do not delete)
│   ├── memory/
│   │   └── scriptures.py   # ChromaDB RAG layer
│   └── skills/
│       ├── browser.py
│       ├── files.py
│       ├── system.py
│       └── vision.py
└── tests/
```

---

## Building a Standalone .exe

```bash
cd rudra
pyinstaller build.spec
# Output: rudra/dist/Rudra/Rudra.exe
```

---

## Current Status

Core pipeline is **feature-complete**: wake word → STT → LLM → TTS → agent tools all
work end-to-end. Scripture RAG is wired but unpopulated (intentional). `.exe` packaging
via PyInstaller is present and tested.

The wake-word model (`models/rudra.onnx`) is a custom-trained ONNX file — do not
delete or retrain; the training data is not in this repository.
