<<<<<<< HEAD
# RUDRA AI — Autonomous Desktop Intelligence

> **Version:** 1.0.0  
> **Architecture:** Electron + React (TypeScript + Tailwind CSS v4) + FastAPI (Python) + Ollama (Qwen 2.5 3B)  
> **Optimized Hardware:** Intel Core i3 10th Gen, 12GB RAM  

---

## 🌟 Overview

**RUDRA AI** is a modern, modular, local-first AI-powered desktop assistant built to act as an intelligent copilot for your computer. It combines:
- **Local AI Conversations & Coding Assistance** powered by Ollama (Qwen 2.5 3B)
- **Real-Time System Monitoring** (CPU, RAM, Storage, Power, Active Processes)
- **Desktop & File Automation** (App launch/close, deep local file search, screenshots)
- **Document Intelligence & Summarization** (PDF, DOCX, PPTX, XLSX)
- **Built-in Vedic wisdom support** via local scripture text files
- **Extensible Plugin Engine** for modular tools

---

## 🛠️ Quick Start

### 1. Prerequisites
- **Python 3.10+** installed
- **Node.js 18+** installed
- **Ollama** installed from [ollama.com](https://ollama.com)
  ```bash
  # Pull the recommended model for 12GB RAM
  ollama pull qwen2.5:3b
  ```

### 2. Installation
```bash
# Install root & frontend dependencies
npm install
cd frontend && npm install && cd ..

# Install Python backend dependencies
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Running the App

#### Start Backend + Web UI (Development):
```bash
npm start
```
- Frontend Web App: `http://localhost:5173`
- FastAPI API Docs: `http://localhost:8000/docs`

#### Start Full Desktop App (Electron):
This runs the built frontend from local files and launches the native desktop shell, not a browser website.
```bash
npm run start:desktop
```

---

## 📂 Project Structure

```
RUDRA_AI/
├── frontend/               # React + Vite + TypeScript + Glassmorphism UI
│   ├── src/
│   │   ├── components/     # Sidebar, Header, etc.
│   │   ├── pages/          # Chat, System, Automation, Memory, Documents, Coding, Settings, Plugins
│   │   ├── services/       # API client + SSE streaming + WebSockets
│   │   ├── stores/         # Zustand global state
│   │   ├── index.css       # Full glassmorphism design system
│   │   ├── App.tsx
│   │   └── main.tsx
├── backend/                # Python FastAPI Server
│   ├── app/
│   │   ├── main.py         # Server entry point
│   │   ├── config.py       # Configuration settings
│   │   ├── routers/        # API Routers (chat, system, automation)
│   │   ├── services/       # Core services (llm_service, system_service, automation_service)
│   │   ├── models/         # Pydantic schemas
│   │   └── database/       # SQLite storage engine
│   └── requirements.txt
├── electron/               # Native Electron Desktop Shell
│   ├── main.cjs
│   └── preload.cjs
└── package.json            # Orchestration scripts
```

---

## 🎨 Features & Capabilities

1. **AI Chat & Streaming Copilot:** Instant real-time text streaming via SSE, syntax-highlighted code blocks with copy-to-clipboard, conversation history & auto-generated session titles.
2. **System Performance Monitor:** Real-time hardware analytics for CPU per-core load, RAM usage, disk storage breakdown, battery status, and process manager.
3. **Desktop Automation:** Launch or terminate local applications, search files across storage, and take screenshots.
4. **Document AI:** Parse and summarize documents for contextual Q&A.
5. **Coding Assistant:** Generate clean, commented code and explain error stack traces.
6. **Plugin Platform:** Extensible framework for third-party tools.

---

Rudra is a Jarvis-style voice assistant that runs in the background on Windows, listens for its name, and speaks back in Hindi, English, or Punjabi. It combines local LLM reasoning (Ollama/Qwen2.5), speech recognition, desktop automation, and a scripture-grounded advice module inspired by Hindu philosophy.

