# RUDRA AI - WP0 Code Audit

**Audited by:** Antigravity (AI coding agent)
**Date:** 2026-10-28
**Spec:** Final Build Spec (WP0-WP9)

---

## 1. What exists in the repo (as-of audit)

No backend/, frontend/, or electron/ directories exist - these were previously deleted per CLAUDE.md.
This build spec requests we re-introduce an Electron + FastAPI + React architecture - a complete rebuild.

### Directory structure found:
- rudra/main.py         - tray + voice loop entry point
- rudra/agent.py        - intent router + tool dispatch (388 lines)
- rudra/llm.py          - Ollama / OpenAI / Anthropic routing (296 lines)
- rudra/stt.py          - faster-whisper STT via SpeechRecognition wrapper
- rudra/tts.py          - edge-tts, Windows MCI audio playback
- rudra/wakeword.py     - openWakeWord + SpeechRecognition fallback
- rudra/hud.py          - pywebview HUD, minimal
- rudra/config.json     - runtime config, no secrets
- rudra/requirements.txt - unpinned dependencies
- rudra/models/         - rudra.onnx - tracked in git, MUST NOT be deleted
- rudra/memory/scriptures.py - ChromaDB RAG, wired but no corpus data
- rudra/skills/browser.py  - webbrowser.open only, NO real browser automation
- rudra/skills/files.py    - search, open, read - good
- rudra/skills/screen.py   - EasyOCR screenshot reader
- rudra/skills/system.py   - open/close apps, system stats - good
- rudra/skills/vision.py   - OpenCV webcam capture + Playwright reverse image
- rudra/hud/hud.html    - single static HUD file for pywebview
- tests/test_agent.py   - 331 lines, comprehensive unit tests

---

## 2. What works (KEEP)

| Component | Status | Decision |
|---|---|---|
| agent.py - intent router + tool dispatch | Works well | Keep and extend |
| llm.py - Ollama/OpenAI/Anthropic routing | Works | Keep, refactor for streaming |
| skills/system.py - open/close apps, stats | Good, Camera URI fix in place | Keep and extend |
| skills/files.py - search, open, read docs | Good | Keep |
| skills/vision.py - OpenCV webcam capture | Works | Keep, fix save path |
| memory/scriptures.py - ChromaDB RAG | Wired, no corpus | Keep as-is |
| models/rudra.onnx | Critical wake word model | NEVER delete |
| config.json | No secrets | Keep, extend |
| tests/test_agent.py | Comprehensive | Keep, add new tests |

---

## 3. What is broken / violates the spec

### 3a. Audio architecture (CRITICAL)
- stt.py uses SpeechRecognition listen() - listen-once sequential pattern
- Every turn waits 1.5s silence before STT even starts (pause_threshold)
- tts.py plays audio with blocking Windows MCI - cannot be interrupted mid-playback
- No AEC - Rudra hears its own voice through speakers, wake word fires on itself
- FIX (WP1/2): Move mic to Electron (AEC + Silero VAD), WebSocket pipeline, streaming

### 3b. No streaming LLM (CRITICAL LATENCY)
- _query_ollama() calls ollama.chat() non-streaming, waits for full response
- On qwen2.5:3b this is 3-8 seconds on i3 before any audio plays
- FIX (WP2): Stream via httpx, split into sentences, speak each sentence immediately

### 3c. wakeword.py fallback uses recognize_google (ONLINE DEPENDENCY)
- Line 110: recognizer.recognize_google() - needs internet, adds 300-800ms latency
- FIX (WP1): Replace with local faster-whisper check

### 3d. SpeechRecognition.listen() blocking loop
- stt.py:87 and wakeword.py:104 - replaced by Silero VAD in Electron renderer

### 3e. No FastAPI backend
- No /ws/voice WebSocket endpoint exists
- ACTION: Create backend/ with app/main.py, voice pipeline, tools

### 3f. No Electron shell
- Was deleted. Must be rebuilt.
- ACTION: Create electron/ with main process, tray, global hotkey, HUD overlay

### 3g. No tool registry / safety tiers
- All tools run without confirmation (close_application can kill processes silently)
- ACTION: WP5 adds Tier.AUTO / Tier.CONFIRM with spoken confirmation

### 3h. skills/browser.py - not real browser automation
- google_search() just calls webbrowser.open()
- YouTube play not implemented
- ACTION: WP6 replaces with Playwright persistent context

### 3i. vision.py saves photos to cwd, not Pictures/Rudra
- capture_photo(filename="capture.jpg") saves relative to CWD
- FIX: Save to Path.home() / "Pictures" / "Rudra"

### 3j. requirements.txt is unpinned
- No version pins - incompatible versions can be silently resolved
- ACTION: Pin to known-good versions

### 3k. .gitignore missing entries
- Missing: node_modules/, *.db, *.sqlite3, logs/, release/, Playwright profile
- ACTION: Extend .gitignore

---

## 4. Grep audit results

### No-popup check: CLEAN
Searched for: messagebox, win10toast, plyer, notification, toast, alert(, showMessageBox, tkinter
Result: NONE FOUND

### Old mic loop: FOUND (scheduled for replacement)
- stt.py:87 - recognizer.listen()
- wakeword.py:104 - recognizer.listen()
- wakeword.py:110 - recognizer.recognize_google()

### Secrets check: CLEAN
- api_key references in llm.py read from env vars only
- No hardcoded tokens, passwords, or absolute C:\Users\... paths
- .env is gitignored, .env.example has no real values

### Subprocess use: SAFE
- skills/system.py - Popen to launch apps (well-controlled)
- llm.py - subprocess.run(["ollama", "run"]) fallback (safe)
- None run LLM-generated shell strings

---

## 5. Architecture gaps (what WP1-WP6 must build)

| Missing piece | WP |
|---|---|
| FastAPI backend with /ws/voice WebSocket | WP1 |
| Silero VAD in Electron renderer | WP1 |
| faster-whisper via PCM bytes (not file) | WP1 |
| rapidfuzz wake word detection | WP1 |
| Streaming Ollama -> sentence splitter -> edge-tts | WP2 |
| TtsPlayer with barge-in stop | WP2 |
| Server-side session + interrupt | WP2 |
| Electron main process (tray, hotkey, backend spawn) | WP3 |
| Electron HUD overlay | WP3 |
| React Voice page UI | WP4 |
| Tool registry with Tier.AUTO / Tier.CONFIRM | WP5 |
| Hardware tools (volume, brightness, lock, power) | WP5 |
| Playwright browser + YouTube play | WP6 |

---

## 6. Before latency numbers (baseline estimate from code analysis)

| Stage | Estimated time on i3 | Bottleneck |
|---|---|---|
| Silence wait (SpeechRecognition pause_threshold) | 1,500 ms | fixed 1.5s tail-silence |
| STT (faster-whisper base, 5-sec audio) | 1,000-1,800 ms | CPU inference |
| LLM (qwen2.5:3b, full response, non-streaming) | 3,000-8,000 ms | waiting for complete response |
| TTS generation (edge-tts, full response) | 800-2,000 ms | network + full response |
| Total (worst case) | ~7-13 s | LLM non-streaming is main killer |

**After WP1-WP2 targets:**

| Stage | Target |
|---|---|
| VAD endpointing (silence detection) | 400 ms |
| STT (PCM bytes, whisper base) | < 1,500 ms |
| LLM first sentence (streaming) | < 2,000 ms |
| TTS first audio chunk | < 700 ms after first sentence |
| Total to first word | < 4,000 ms |

---

## 7. Key decisions

1. rudra/ Python package is KEPT. Skills/agent/llm/memory reused in FastAPI backend.
2. New layout adds: backend/, electron/, frontend/ alongside existing rudra/
3. rudra/main.py kept as legacy fallback (gated behind --legacy flag)
4. rapidfuzz added to backend requirements for fuzzy wake word matching
5. pyttsx3 added as offline TTS fallback

---

*After-latency numbers will be added after WP7 (Latency Pass).*
