/**
 * RUDRA AI - Electron Main Process
 * Creates desktop app window, manages background system tray & wake-word popups.
 */

const { app, BrowserWindow, ipcMain, shell, Tray, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const WebSocket = require('ws');

let mainWindow = null;
let backendProcess = null;
let eventWs = null;
let tray = null;

const isDev = process.env.NODE_ENV === 'development';

function startBackend() {
  console.log('Starting Python FastAPI Backend...');
  const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
  const backendScript = path.join(__dirname, '../backend/app/main.py');

  backendProcess = spawn(pythonExecutable, [backendScript], {
    cwd: path.join(__dirname, '../backend'),
    stdio: 'inherit',
    shell: true,
  });

  backendProcess.on('error', (err) => {
    console.error('Failed to start FastAPI backend:', err);
  });
}

function connectWakeWordListener() {
  // Connect WebSocket to Python backend event stream
  const wsUrl = 'ws://127.0.0.1:8000/api/system/events';

  function connect() {
    eventWs = new WebSocket(wsUrl);

    eventWs.on('open', () => {
      console.log('⚡ Connected to RUDRA AI Background Event Stream (Wake Word Active)');
    });

    eventWs.on('message', (data) => {
      try {
        const event = JSON.parse(data.toString());
        if (event.type === 'WAKE_WORD_TRIGGERED') {
          console.log('⚡ Wake word "Rudra" detected! Opening desktop window...');
          showWindow();
        }
      } catch (err) {
        // Skip parse errors
      }
    });

    eventWs.on('close', () => {
      // Auto-reconnect after 3 seconds if disconnected
      setTimeout(connect, 3000);
    });

    eventWs.on('error', () => {
      // Silently handle error before reconnect
    });
  }

  // Delay initial connection slightly so backend is ready
  setTimeout(connect, 3000);
}

function showWindow() {
  if (!mainWindow) {
    createWindow();
    return;
  }

  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();

  // Momentary always-on-top to force bring window over other full-screen apps
  mainWindow.setAlwaysOnTop(true);
  setTimeout(() => {
    if (mainWindow) mainWindow.setAlwaysOnTop(false);
  }, 500);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 900,
    minHeight: 600,
    title: 'RUDRA AI — Autonomous Desktop Intelligence',
    backgroundColor: '#0a0a0f',
    autoHideMenuBar: true,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    const indexPath = path.join(__dirname, '../frontend/dist/index.html');
    mainWindow.loadFile(indexPath).catch((err) => {
      console.error('Failed to load production UI file:', err);
    });
  }

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error('Production UI failed to load:', errorCode, errorDescription, validatedURL);
  });

  mainWindow.webContents.on('did-finish-load', () => {
    console.log('Production UI loaded:', mainWindow.webContents.getURL());
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
  });

  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log(`Renderer console [${level}] ${sourceId}:${line} ${message}`);
  });

  mainWindow.once('ready-to-show', () => {
    console.log('Window is ready to show.');
    mainWindow.show();
    mainWindow.focus();
  });

  // Minimize to system tray instead of closing completely if tray is active
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      console.log('RUDRA AI minimized to background tray. Say "Rudra" to wake up anytime!');
      return false;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  // System tray menu so user can quit or restore anytime
  try {
    const iconPath = path.join(__dirname, '../frontend/dist/favicon.svg');
    tray = new Tray(iconPath);
    const contextMenu = Menu.buildFromTemplate([
      { label: 'Open RUDRA AI', click: () => showWindow() },
      { label: 'Say "Rudra" to Wake Up', enabled: false },
      { type: 'separator' },
      {
        label: 'Quit RUDRA AI',
        click: () => {
          app.isQuitting = true;
          app.quit();
        },
      },
    ]);
    tray.setToolTip('RUDRA AI - Listening for "Rudra" wake word');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => showWindow());
  } catch (err) {
    console.log('Tray creation skipped (icon not found or headless environment)');
  }
}

app.whenReady().then(() => {
  // Always start in background on Windows boot
  app.setLoginItemSettings({
    openAtLogin: true,
    openAsHidden: false,
  });

  startBackend();
  createWindow();
  createTray();
  connectWakeWordListener();

  if (isDev && mainWindow) {
    mainWindow.show();
  }

  app.on('activate', () => {
    showWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Keep app alive in background for wake word unless explicitly quit
  }
});
