# CLAUDE.md — Rudra AI Project Context

This file is the persistent context document for any Claude Code (or similar AI
coding assistant) session on this project. Read this before making changes.

---

## What This Project Is

**Rudra** is a local, voice-activated desktop assistant for Windows. It runs as a
system-tray application, listens continuously for its custom wake word ("Rudra"),
transcribes speech, routes the request through an LLM or an agent tool, and speaks
the response back — all entirely on-device.

It is **not** a web app, chat UI, or Electron app. A previous version used that
stack; it was deleted. What remains is a single Python project under `rudra/`.

---

## Directory Layout

```
RUDRA-AI-/
├── CLAUDE.md               <- this file (persistent context)
├── README.md               <- user-facing setup guide
├── .gitignore
├── rudra/                  <- entire application lives here
│   ├── main.py             <- entry point; RudraTray class + signal handling
│   ├── agent.py            <- intent routing + tool dispatch
│   ├── llm.py              <- Ollama / OpenAI / Anthropic routing
│   ├── stt.py              <- faster-whisper speech-to-text
│   ├── tts.py              <- edge-tts text-to-speech (async, threaded)
│   ├── wakeword.py         <- openWakeWord listener thread
│   ├── config.json         <- runtime config (model, threads, voices, etc.)
│   ├── requirements.txt    <- pip dependencies
│   ├── build.spec          <- PyInstaller build spec
│   ├── tray_icon.ico       <- system-tray icon
│   ├── models/
│   │   └── rudra.onnx      <- trained wake-word model -- DO NOT DELETE / RETRAIN
│   ├── memory/
│   │   └── scriptures.py   <- ChromaDB RAG interface for scripture corpus
│   ├── skills/
│   │   ├── browser.py      <- google_search, open_url
│   │   ├── files.py        <- open_file, search_file
│   │   ├── system.py       <- open/close apps, system stats
│   │   └── vision.py       <- screenshot capture
│   ├── data/               <- (empty) placeholder for scripture text files
│   └── rudra_chroma/       <- ChromaDB persistence dir (auto-created)
└── tests/
    └── test_agent.py
```

---

## Tech Stack

| Component | Library |
|-----------|---------|
| Wake word | openWakeWord + custom rudra.onnx (ONNX) |
| STT | faster-whisper (base model by default) |
| TTS | edge-tts (Microsoft Neural voices, async) |
| LLM | Ollama (local) -- see Machine Profiles below |
| RAG | ChromaDB + sentence-transformers |
| Tray | pystray + Pillow |
| Packaging | PyInstaller (build.spec) |
| Automation | pyautogui, keyboard, psutil, subprocess |

---

## Machine Profiles

The project runs on two different machines with different hardware constraints.
Edit `rudra/config.json` to match the active machine.

### Machine A — Primary Dev Machine (i3 10th Gen, 12 GB RAM)
- Model: `qwen2.5:3b-instruct-q4_K_M`
- Threads: 4
- Config: `"ollama_model": "qwen2.5:3b-instruct-q4_K_M"`, `"ollama_threads": 4`

### Machine B — Secondary / Low-RAM Machine
- Model: `tinyllama:latest` or `phi3:mini`
- Threads: 2
- Config: adjust `ollama_model` and `ollama_threads` accordingly

> `config.json` is committed; change the model there rather than setting env vars
> unless you are doing a one-off override via `LLM_PROVIDER` / `OPENAI_API_KEY`.

---

## Key Design Decisions

### Wake word model (models/rudra.onnx)
This ONNX model was trained specifically for the word "Rudra" using openWakeWord's
training pipeline. **Do not delete it and do not retrain it** -- the training
dataset and pipeline are not in this repo. If lost, the model must be sourced from
the original training run.

### Scripture RAG (ChromaDB)
`memory/scriptures.py` implements a ChromaDB-backed retrieval module for Vedic
scripture passages. The **data ingestion is intentionally deferred** -- the `data/`
directory is currently empty. This is a design choice, not a bug. When scripture
texts are ready to load, run the ingestion script (to be added to `scripts/`).
The RAG pipeline is fully wired; it simply returns zero results on empty corpus
(handled gracefully in `main.py`).

### Dual import paths in agent.py
`agent.py` tries `rudra.skills.*` first (for `python -m rudra` invocation), then
falls back to `skills.*` (for `python main.py` from inside `rudra/`). Both are
intentional. Do not collapse this into a single path.

### LLM provider routing
`llm.py` supports `ollama` (default), `openai`, and `anthropic` backends, selected
by `config.json:llm_provider` or the `LLM_PROVIDER` env var. API keys read from
`.env` (not committed). See `.env.example`.

---

## Running from Source

```bash
cd rudra
pip install -r requirements.txt
# Ensure Ollama is installed and the model is pulled:
ollama pull qwen2.5:3b-instruct-q4_K_M
python main.py
```

The tray icon appears in the system tray. Right-click -> Quit to exit.

---

## Packaging (.exe)

```bash
cd rudra
pyinstaller build.spec
```

Output: `rudra/dist/Rudra/Rudra.exe` (folder-mode build, not a single file).

If a **runtime** missing-module error appears in the packaged .exe (not at build
time), add `collect_all("package_name")` to the loop in `build.spec` -- same
pattern as the five packages already there. Do not add speculatively.

---

## Known Issues / Gotchas

- **wakeword false-positive rate**: The model is sensitive. If false positives are
  too frequent, increase the threshold in `wakeword.py`.
- **edge-tts requires internet**: The TTS backend streams from Microsoft's servers.
  Offline fallback is not implemented.
- **PyAudio on Windows**: Requires PortAudio. Install via the `pyaudio` wheel from
  the Christoph Gohlke repo if pip fails on Windows.
- **faster-whisper first run**: Downloads model weights (~150 MB for `base`). Ensure
  internet access on first run from source; for packaged .exe, weights are fetched
  at runtime to the user's cache.

---

## What Was Deleted (Do Not Re-Add)

- `frontend/` -- React + Vite + TypeScript UI (deleted, not needed)
- `backend/` -- FastAPI server (deleted, not needed)
- `electron/` -- Electron shell (deleted, not needed)
- Root `package.json` -- Node orchestration scripts (deleted)
- `node_modules/`, `package-lock.json` -- Node artifacts (never existed in git)

---

## Git Workflow Notes

- `main` is the only branch; commit directly.
- `rudra/build/` and `rudra/dist/` are gitignored (PyInstaller output).
- `rudra/rudra_chroma/` should be gitignored (auto-generated DB).
- `models/rudra.onnx` is **tracked by git** -- it must survive machine changes.
