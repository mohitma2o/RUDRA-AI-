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
