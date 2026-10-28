import { app, BrowserWindow, globalShortcut, ipcMain, Menu, Tray } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import * as http from 'http';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let backendProcess: ChildProcess | null = null;
const isDev = process.env.NODE_ENV !== 'production' && !app.isPackaged;

function checkBackendHealth(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get('http://127.0.0.1:8000/health', (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function spawnBackendIfNeeded(): Promise<void> {
  const isRunning = await checkBackendHealth();
  if (isRunning) {
    console.log('[Backend] Existing backend detected on port 8000.');
    return;
  }

  const repoRoot = path.resolve(__dirname, '../../');
  const backendDir = path.join(repoRoot, 'backend');

  console.log('[Backend] Spawning FastAPI backend...');
  backendProcess = spawn(
    'python',
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
    {
      cwd: backendDir,
      env: { ...process.env, PYTHONPATH: repoRoot },
      shell: true,
      stdio: 'inherit',
    }
  );

  backendProcess.on('error', (err) => {
    console.error('[Backend] Failed to start backend:', err);
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 440,
    height: 640,
    show: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: false,
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../../frontend/dist/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function toggleWindow(): void {
  if (!mainWindow) {
    createWindow();
    return;
  }
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

function createTray(): void {
  const iconPath = path.resolve(__dirname, '../../rudra/tray_icon.ico');
  try {
    tray = new Tray(iconPath);
  } catch (err) {
    console.warn('[Tray] Could not load tray icon, continuing without it:', err);
    return;
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Toggle HUD (Ctrl+Shift+Space)',
      click: () => toggleWindow(),
    },
    {
      label: 'Show HUD',
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      },
    },
    {
      label: 'Hide HUD',
      click: () => mainWindow?.hide(),
    },
    { type: 'separator' },
    {
      label: 'Quit Rudra',
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setToolTip('Rudra AI Desktop Assistant');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => toggleWindow());
}

// IPC Handlers
ipcMain.on('window-hide', () => {
  mainWindow?.hide();
});

ipcMain.on('window-minimize', () => {
  mainWindow?.minimize();
});

ipcMain.on('window-close', () => {
  mainWindow?.hide();
});

ipcMain.handle('get-version', () => {
  return app.getVersion();
});

// App Lifecycle
app.whenReady().then(async () => {
  await spawnBackendIfNeeded();
  createWindow();
  createTray();

  // Register Global Hotkey
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    toggleWindow();
  });
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (backendProcess) {
    try {
      backendProcess.kill();
    } catch {}
  }
});
