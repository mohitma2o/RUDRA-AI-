# Agent Work Progress

## WP-A0 — Documentation reset

- Rewrote `CLAUDE.md` to document the current Electron + React + FastAPI
  application and distinguish it from the retained legacy `rudra/` tray app.
- Marked `AUDIT.md` as a historical 2026-10-28 audit.
- Preserved the `rudra/models/rudra.onnx` constraint and documented privacy and
  online Edge TTS behavior.
- Verified the documentation changes against the repository structure and the
  attached work guide. No tests were needed for this documentation-only package.
- Not yet verified: packaged-app behavior, clean-machine installation, and
  live Windows audio/hardware behavior.

## WP-A1 — Development loop

- Made the root `dev` script compile Electron before starting the backend,
  frontend, and Electron processes.
- Bound Vite and the development backend to `127.0.0.1`; aligned Electron's
  dev URL, voice WebSocket URL, and `wait-on` check to IPv4 loopback.
- Removed the frontend's self-referencing `file:..` dependency and its lockfile
  link entries.
- Verified `npm run build` (frontend TypeScript/Vite build and Electron
  TypeScript compile) and confirmed no stale localhost URLs or self-dependency
  remain in the relevant files.
- Not yet verified: the complete interactive `npm run dev` launch and the
  fresh-clone installation acceptance test.

## WP-A2 — Electron lifecycle and backend launcher

- Added single-instance behavior, safe external navigation handling, sandboxed
  renderer settings, app identity, Start with Windows tray setting, and
  packaged/dev resource paths.
- Reworked backend startup to use `shell: false`, a loopback port, per-launch
  token, user-data directory, health polling, backend log,
  failure/restart status, and Windows process-tree termination on quit.
- Exposed backend config/status/log IPC through the preload bridge; the HUD now
  reports startup/failure state and offers a log action. Added a renderer CSP.
- Verified `npm run build`, `python -m pytest tests -q` (66 passed), and a live
  `npm run dev` smoke test: Vite, Electron, and FastAPI started and `/health`
  returned HTTP 200. Confirmed the backend endpoint was unavailable after
  stopping the smoke-test process tree.
- Not yet verified: packaged runtime resource paths, clean-machine installer,
  Windows startup setting, process-tree behavior in a packaged release, or
  runtime CSP/navigation behavior in a visual UI test.

## WP-A3 — Frozen backend foundations

- Added `backend/app/paths.py` for immutable bundled resources and writable
  per-user data, merged default/user config loading, atomic user-config saving,
  and user-data storage for the Playwright profile.
- Added a frozen-safe `backend/run.py`, a pinned PyInstaller build dependency,
  a one-folder spec, and a model-download step for bundling faster-whisper
  `base`. The core dependency list now excludes unused, heavyweight optional
  packages; Playwright, ChromaDB, sentence-transformers, EasyOCR, and OpenCV
  are in `backend/requirements-optional.txt`.
- Added `python-pptx` to core dependencies for the planned PPTX document
  extraction feature. Added backend build/model output paths to `.gitignore`.
- Verified `npm run build` and `python -m pytest tests -q` (69 passed).
- Not yet verified: installing the split requirements from scratch, downloading
  Whisper weights, PyInstaller execution, frozen one-folder startup, or the
  resulting executable size. The model download/build was not run because it
  requires network access and produces a large model bundle.

## WP-A4 — Windows installer foundations

- Added the pinned `electron-builder` 26.18.0 dependency and NSIS configuration,
  including the requested app ID, product name, `release/` output, resources,
  icon, and installer directory options. Added the `dist` script.
- Replaced Google Fonts links with pinned local Outfit and JetBrains Mono
  packages; the production build now emits local font assets.
- Verified `npm run build`, `npx electron-builder --version` (26.18.0), and
  `npm audit --omit=dev` (no production dependency advisories).
- npm reports Node-engine warnings for transitive `@electron/rebuild` and
  `node-abi` requiring Node 22.12+ while the current environment is Node 20.18;
  the builder CLI itself runs. Full NSIS output is not yet verified because it
  requires the Whisper model download and frozen backend build. The full npm
  audit currently reports 8 development-toolchain advisories (6 moderate,
  2 high); no `npm audit fix` was applied.

## WP-A5 — First-run Ollama setup

- Added authenticated `/api/setup/status` and model-pull SSE endpoints. Status
  reports Ollama availability, installed/required models, STT readiness, and
  online TTS connectivity.
- Added a non-blocking HUD setup notice with Ollama download link, recheck,
  model download progress, and explicit error reporting. Setup calls use the
  per-launch bearer token.
- Changed `npm run dev` to start only Vite and Electron; Electron owns backend
  startup, avoiding a duplicate Python server and port conflict.
- Verified `npm run build`, `python -m pytest tests -q` (70 passed), and a live
  dev smoke test: `/health` returned HTTP 200, setup status without a token
  returned HTTP 401, and the backend stopped after the test process tree was
  terminated.
- Not yet verified: Ollama installation/model download progress against a live
  Ollama server or live TTS network status. Production `file://` origin policy
  and API/WebSocket authentication are covered in WP-D1.

## WP-B1 — Voice client reliability

- Replaced `ScriptProcessorNode` with an `AudioWorklet` capture path and
  separate capture/playback audio contexts. The processor is copied to the
  production frontend root and served from the same origin.
- Reworked the voice hook to avoid whole-store subscriptions, use stable
  effects, apply configuration changes immediately, keep a 300 ms pre-roll,
  estimate an adaptive noise floor, ignore speech shorter than 250 ms, cap
  utterances at 15 seconds, and endpoint after 450 ms of silence.
- Added FIFO TTS playback; barge-in clears queued audio and interrupts the
  backend. Playback state is local and is not overwritten by an early server
  `idle` event.
- Verified `npm run build`; confirmed `frontend/dist/capture-worklet.js` is
  emitted. Python regression suite was green immediately before the final
  frontend-only adjustments (70 passed).
- Not yet verified: microphone permission/audio on physical Windows hardware,
  actual sequential audio playback, adaptive VAD behavior in noisy rooms, or
  voice barge-in latency.

## WP-B2 — Voice backend reliability and model selection

- Made fast-path matching anchored and table-driven so incidental words such
  as "screenshots" or "replay" no longer trigger tools. Added regression tests
  for false positives, punctuation, and existing command forms.
- Avoided reloading the Whisper model when its configured size is unchanged;
  guarded cancelled and superseded voice-turn callbacks from reporting stale
  idle states or reading an exception from a cancelled task.
- Added separate `ollama_voice_model` and `ollama_doc_model` settings. Startup
  and setup status now use only the voice model, and legacy per-user
  `ollama_model` overrides migrate to the voice-model setting. The document
  model is selected on demand by the document workflow.
- Corrected timing measurements to capture the first streamed LLM token and
  full-turn duration, emit timing events, and print latency metrics to the
  backend log.
- Verified `python -m pytest tests -q` (75 passed, 16 subtests) and editor
  diagnostics for the changed Python files. Two existing FastAPI lifecycle
  deprecation warnings remain.
- Not yet verified: live Ollama voice-model warm-up, document summarization
  model loading, or latency measurements against a running Ollama/TTS stack.

## WP-B3 — Persistent browser automation

- Moved Playwright startup and all synchronous browser operations to one
  dedicated worker thread. YouTube searches now reuse a persistent context and
  page rather than launching a new browser for every request.
- Added serialized requests, cancellation-safe futures, explicit fallback
  messages when Playwright is unavailable, and graceful context shutdown with
  the backend.
- Added a mocked runtime test covering single-thread ownership, one persistent
  context, page reuse, and shutdown. Verified `python -m pytest tests -q`
  (76 passed, 16 subtests) and editor diagnostics for the changed Python files.
- Not yet verified: launching the bundled Playwright browser or interacting
  with YouTube on a real Windows desktop.

## WP-B4 — Allowlisted desktop and file tools

- Added backend tools for opening/searching/reading files and opening folders.
  Every supplied file or folder path is resolved and checked against
  `ALLOWED_FILE_ROOTS`; symlink escapes are rejected, and recursive searches
  never follow directory symlinks or leave the approved roots.
- Ported the legacy application open/close operations. Closing an application
  now uses the existing confirmation tier. Added explicit voice fast paths for
  file, folder, and application commands.
- Document reads support TXT, Markdown, DOCX, and PDF and remain capped at
  3,000 characters. Updated the README with the available commands and file
  access boundary.
- Verified `python -m pytest tests -q` (83 passed, 1 skipped, 16 subtests) and
  editor diagnostics. Symlink escape coverage is skipped on environments where
  Windows disallows creating test symlinks.
- Not yet verified: launching applications and opening files/folders on a
  physical Windows desktop.

## Phase 3 — Document workspace

- Added authenticated upload, job status, cancellation, and replayable SSE
  progress APIs. Documents are size/type limited, extracted for TXT, Markdown,
  PDF, DOCX, and PPTX, chunked, summarized in map/reduce passes, and removed
  from temporary storage after processing.
- Added a per-user SQLite notes library with rename/delete and Markdown/text
  exports. The document model loads only when needed. A voice command can
  summarize an allowlisted local document, and the HUD now opens a workspace
  for uploads, progress, and note management.
- Added the multipart upload dependency and included it in the frozen backend
  spec; centralized config loading for voice and document model selection.
- Verified the focused document/config tests (23 passed) and `npm run build`.
- Not yet verified: real Ollama document summarization, physical Electron
  uploads/exports, or Windows frozen-backend behavior.

## WP-D1 — Local API perimeter

- The voice WebSocket now checks the renderer origin and authenticates a
  first-frame token before creating a voice session. The token is not placed
  in the WebSocket URL. HTTP APIs continue to require the per-launch token.
- Restricted CORS to the two loopback development origins and Electron's
  `file://` origin (`null`), and allowed only the methods used by the app,
  including document-note PATCH and DELETE operations.
- Added tests for valid/invalid WebSocket tokens, rejected origins, and
  development and file-origin CORS preflights. The full Python suite passes.
- Not yet verified: requests from a packaged Electron build on a clean Windows
  machine.

## WP-D2 — Rotating backend logs

- Added synchronous size-based log rotation for Electron-captured backend
  output: a 5 MiB active file and up to three retained backups. Rotation/write
  errors are surfaced to the Electron console.
- Added Node tests for rotation, retention, and normal append behavior.
  `npm run test:electron` passes (2 tests).

## WP-E — Final acceptance and CI

- Added a Windows GitHub Actions workflow that installs pinned backend and
  desktop dependencies, runs the Python and Electron logger tests, and builds
  the frontend and Electron application.
- Final local verification: `python -m pytest tests -q` (93 passed, 1 skipped,
  16 subtests), `npm run test:electron` (2 passed), `npm run build`, editor
  diagnostics for changed application files, and `git diff --check`.
- Still outstanding: live Ollama summaries, physical Windows audio/desktop
  interaction, and a packaged PyInstaller/Electron installer smoke test. These
  require local services, hardware, and/or the large Whisper model download.
