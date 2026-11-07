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
