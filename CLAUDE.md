# Rudra AI — Project Context

Read this document before changing the project. It describes the current
Electron + React + FastAPI application and the retained legacy Python tray app.

## What this project is

Rudra is a Windows desktop voice assistant. The current desktop application is
an Electron shell with a React HUD and a local FastAPI backend. The backend
handles speech transcription, wake-word matching, LLM responses, speech
synthesis, and registered desktop tools. Ollama is an external local-runtime
prerequisite. Edge TTS uses Microsoft's online service; do not describe all
speech processing as offline.

The `rudra/` Python package is retained as a legacy tray application. It is not
the current Electron backend and should not be confused with `backend/`.

## Repository layout

```
RUDRA-AI-/
├── backend/                 # Current FastAPI service
│   └── app/
│       ├── main.py          # HTTP/WebSocket routes and voice session
│       ├── voice/           # STT, wake matching, streaming voice pipeline
│       └── tools/           # Tool registry, browser and hardware tools
├── electron/                # Electron main process and preload bridge
├── frontend/                # React/Vite renderer and voice HUD
├── rudra/                   # Retained legacy Python tray app
│   ├── models/rudra.onnx    # Custom wake-word model; preserve it
│   ├── memory/              # Legacy scripture RAG
│   └── skills/              # Legacy desktop skills
├── tests/                   # Python regression tests
├── package.json             # Electron development/build scripts
├── README.md                # User setup and feature guide
└── AUDIT.md                 # Historical audit; not current architecture
```

## Current runtime

- The Electron main process launches the FastAPI backend and opens the React
  HUD. In development the renderer is served by Vite.
- The renderer captures microphone audio, applies voice activity detection,
  and communicates with the backend over `/ws/voice`.
- The backend uses faster-whisper for speech recognition, rapidfuzz for
  transcript wake-word matching, Ollama for local LLM inference, and edge-tts
  for online speech synthesis with an offline fallback where configured.
- The backend tool registry and safety tiers are in `backend/app/tools/`.
- `rudra/` remains independently runnable as a legacy tray app; its agent,
  skills, memory and configuration are not automatically used by the backend.

## Development

See `README.md` for prerequisites and setup. The current project has both
Python and Node dependencies:

```powershell
python -m pytest tests -q
npm install
npm --prefix frontend install
npm run build
```

Use the project scripts in the root `package.json` for development and
packaging. Do not claim that a packaged installer works until the packaged
application has actually been tested on Windows.

## Data, configuration, and privacy

- Never commit API keys, access tokens, or other secrets. Use environment
  variables or a local, ignored `.env` file.
- Keep writable runtime data out of an installed, read-only application
  directory; use the configured user data directory when available.
- Treat document text, transcripts, and local file paths as private. Avoid
  logging their contents. Document summarization must not execute instructions
  contained in the document.
- Edge TTS sends text to Microsoft's service. Be explicit about this wherever
  privacy or offline operation is described.
- Ollama is local but must be installed separately unless packaging is
  deliberately changed.

## Important constraints

- **Never delete or retrain `rudra/models/rudra.onnx`.** It was trained for
  Rudra and its original training data/pipeline are not stored in this repo.
- Preserve the distinct roles and import paths of `backend/` and `rudra/`.
- Keep Windows-only operations guarded so unit tests can run on other systems.
- Do not add large optional dependencies to the core runtime without a feature
  that requires them.
- `AUDIT.md` is a historical record. Verify current code before relying on its
  findings.
