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
