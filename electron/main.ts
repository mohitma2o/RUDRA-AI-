import { createHash, randomBytes } from 'crypto';
import { mkdirSync } from 'fs';
import { writeFile } from 'fs/promises';
import { ChildProcess, spawn } from 'child_process';
import { app, BrowserWindow, dialog, globalShortcut, ipcMain, Menu, shell, Tray } from 'electron';
import * as http from 'http';
import * as path from 'path';
import { createServer } from 'net';
import { appendRotatingLog } from './backendLogger';

type BackendStatus = 'starting' | 'ready' | 'failed' | 'restarting';

interface BackendConfig {
  httpBase: string;
  wsUrl: string;
  token: string;
}

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let backendProcess: ChildProcess | null = null;
let backendConfig: BackendConfig | null = null;
let backendLogPath = '';
let restartCount = 0;
let restartScheduled = false;
let isQuitting = false;
const isDev = !app.isPackaged;

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!mainWindow) return;
    if (!mainWindow.isVisible()) mainWindow.show();
    mainWindow.focus();
  });
}

function sendBackendStatus(status: BackendStatus, message?: string): void {
  mainWindow?.webContents.send('backend-status', { status, message });
}

function appendBackendLog(data: Buffer | string): void {
  if (!backendLogPath) return;
  try {
    appendRotatingLog(backendLogPath, data);
  } catch (error) {
    console.error('[Backend] Could not write backend log:', error);
  }
}

function findAvailablePort(preferredPort: number): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', (error: NodeJS.ErrnoException) => {
      if (preferredPort !== 0 && error.code === 'EADDRINUSE') {
        findAvailablePort(0).then(resolve, reject);
      } else {
        reject(error);
      }
    });
    server.listen(preferredPort, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address === 'string') {
        server.close();
        reject(new Error('Could not determine the backend port.'));
        return;
      }
      server.close((error) => {
        if (error) reject(error);
        else resolve(address.port);
      });
    });
  });
}

function checkBackendHealth(): Promise<boolean> {
  const config = backendConfig;
  if (!config) return Promise.resolve(false);
  return new Promise((resolve) => {
    const req = http.get(`${config.httpBase}/health`, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk: string) => { body += chunk; });
      res.on('end', () => {
        try {
          const health = JSON.parse(body) as { status?: string; instance?: string };
          const expected = createHash('sha256').update(config.token).digest('hex').slice(0, 16);
          resolve(res.statusCode === 200 && health.status === 'ok' && health.instance === expected);
        } catch {
          resolve(false);
        }
      });
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function waitForBackend(child: ChildProcess, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    let finished = false;
    const complete = (ready: boolean) => {
      if (finished) return;
      finished = true;
      clearInterval(timer);
      child.removeListener('exit', onExit);
      resolve(ready);
    };
    const onExit = () => complete(false);
    const timer = setInterval(async () => {
      if (child.exitCode !== null || child.killed) {
        complete(false);
      } else if (await checkBackendHealth()) {
        complete(true);
      } else if (Date.now() >= deadline) {
        complete(false);
      }
    }, 500);
    child.once('exit', onExit);
  });
}

function scheduleBackendRestart(): void {
  if (isQuitting || restartScheduled) return;
  if (restartCount >= 3) {
    sendBackendStatus('failed', `Backend stopped. See the log at ${backendLogPath}`);
    return;
  }
  restartScheduled = true;
  restartCount += 1;
  const delayMs = 1000 * 2 ** (restartCount - 1);
  sendBackendStatus('restarting', `Restart attempt ${restartCount} of 3`);
  setTimeout(() => {
    restartScheduled = false;
    void startBackend(true);
  }, delayMs);
}

async function startBackend(isRestart = false): Promise<void> {
  if (isQuitting || backendProcess) return;

  sendBackendStatus(isRestart ? 'restarting' : 'starting');
  try {
    if (!backendConfig) {
      const port = await findAvailablePort(8000);
      backendConfig = {
        httpBase: `http://127.0.0.1:${port}`,
        wsUrl: `ws://127.0.0.1:${port}/ws/voice`,
        token: randomBytes(32).toString('hex'),
      };
    }

    const userDataDir = app.getPath('userData');
    const logsDir = path.join(userDataDir, 'logs');
    mkdirSync(logsDir, { recursive: true });
    backendLogPath = path.join(logsDir, 'backend.log');
    appendBackendLog(`\n[${new Date().toISOString()}] Starting backend.\n`);

    const repoRoot = isDev ? path.resolve(__dirname, '../../') : app.getAppPath();
    const backendDir = path.join(repoRoot, 'backend');
    const executable = path.join(process.resourcesPath, 'backend', 'rudra-backend.exe');
    const args = isDev
      ? ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', new URL(backendConfig.httpBase).port]
      : [];
    const command = isDev ? (process.env.PYTHON || 'python') : executable;

    const child = spawn(command, args, {
      cwd: isDev ? backendDir : path.dirname(executable),
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        RUDRA_PORT: new URL(backendConfig.httpBase).port,
        RUDRA_TOKEN: backendConfig.token,
        RUDRA_DEV: isDev ? '1' : '0',
        RUDRA_DATA_DIR: userDataDir,
      },
      shell: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    backendProcess = child;
    child.stdout?.on('data', appendBackendLog);
    child.stderr?.on('data', appendBackendLog);
    child.on('error', (error) => {
      appendBackendLog(`[${new Date().toISOString()}] Backend launch error: ${error.message}\n`);
      if (backendProcess === child) backendProcess = null;
      sendBackendStatus('failed', `Could not start the backend. See ${backendLogPath}`);
      scheduleBackendRestart();
    });
    child.on('exit', (code, signal) => {
      appendBackendLog(`[${new Date().toISOString()}] Backend exited (code=${code}, signal=${signal}).\n`);
      if (backendProcess === child) backendProcess = null;
      if (!isQuitting && !manualRestartInProgress) {
        sendBackendStatus('failed', `Backend exited. See ${backendLogPath}`);
        scheduleBackendRestart();
      }
    });

    const ready = await waitForBackend(child, 120_000);
    if (ready) {
      restartCount = 0;
      sendBackendStatus('ready');
    } else if (!isQuitting && child.exitCode === null) {
      appendBackendLog(`[${new Date().toISOString()}] Backend readiness timed out.\n`);
      sendBackendStatus('failed', `Backend did not become ready. See ${backendLogPath}`);
      killBackend();
    }
  } catch (error) {
    appendBackendLog(`[${new Date().toISOString()}] Backend startup error: ${String(error)}\n`);
    sendBackendStatus('failed', `Could not start the backend. See ${backendLogPath}`);
    scheduleBackendRestart();
  }
}

function killBackend(): void {
  const child = backendProcess;
  if (!child?.pid) return;
  backendProcess = null;
  if (process.platform === 'win32') {
    const killer = spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], {
      windowsHide: true,
      stdio: 'ignore',
    });
    killer.on('error', (error) => {
      appendBackendLog(`Could not terminate backend process tree: ${error.message}\n`);
    });
  } else {
    child.kill('SIGTERM');
  }
}

let manualRestartInProgress = false;

async function restartBackend(): Promise<void> {
  if (isQuitting) throw new Error('Rudra is shutting down.');
  restartScheduled = false;
  restartCount = 0;
  const previous = backendProcess;
  if (previous) {
    manualRestartInProgress = true;
    try {
      const stopped = new Promise<void>((resolve, reject) => {
        if (previous.exitCode !== null) {
          resolve();
          return;
        }
        const timer = setTimeout(() => {
          previous.removeListener('exit', onExit);
          reject(new Error('The previous backend process did not stop.'));
        }, 10_000);
        const onExit = () => {
          clearTimeout(timer);
          resolve();
        };
        previous.once('exit', onExit);
      });
      killBackend();
      await stopped;
    } finally {
      manualRestartInProgress = false;
    }
  }
  await startBackend(true);
}

function isAllowedAppUrl(url: string): boolean {
  if (isDev) return url.startsWith('http://127.0.0.1:5173/');
  return url.startsWith('file://');
}

function openExternalUrl(url: string): void {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      void shell.openExternal(parsed.toString());
    }
  } catch (error) {
    console.warn('[Electron] Refusing invalid external URL:', error);
  }
}

function createWindow(): void {
  const iconPath = isDev
    ? path.resolve(__dirname, '../../rudra/tray_icon.ico')
    : path.join(process.resourcesPath, 'tray_icon.ico');
  mainWindow = new BrowserWindow({
    width: 560,
    height: 820,
    show: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: false,
    hasShadow: true,
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    openExternalUrl(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedAppUrl(url)) {
      event.preventDefault();
      openExternalUrl(url);
    }
  });

  if (isDev) {
    void mainWindow.loadURL('http://127.0.0.1:5173');
  } else {
    void mainWindow.loadFile(path.join(__dirname, '../../frontend/dist/index.html'));
  }

  mainWindow.once('ready-to-show', () => mainWindow?.show());
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
  const iconPath = isDev
    ? path.resolve(__dirname, '../../rudra/tray_icon.ico')
    : path.join(process.resourcesPath, 'tray_icon.ico');
  try {
    tray = new Tray(iconPath);
  } catch (error) {
    console.warn('[Tray] Could not load tray icon:', error);
    return;
  }

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Toggle HUD (Ctrl+Shift+Space)', click: toggleWindow },
    { label: 'Show HUD', click: () => { mainWindow?.show(); mainWindow?.focus(); } },
    { label: 'Hide HUD', click: () => mainWindow?.hide() },
    {
      label: 'Start with Windows',
      type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked }),
    },
    { type: 'separator' },
    { label: 'Quit Rudra', click: () => app.quit() },
  ]);
  tray.setToolTip('Rudra AI Desktop Assistant');
  tray.setContextMenu(contextMenu);
  tray.on('click', toggleWindow);
}

ipcMain.on('window-hide', () => mainWindow?.hide());
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-close', () => mainWindow?.hide());
ipcMain.handle('get-version', () => app.getVersion());
ipcMain.handle('get-backend-config', () => backendConfig);
ipcMain.handle('restart-backend', () => restartBackend());
ipcMain.handle('save-file', async (_event, request: unknown) => {
  if (!request || typeof request !== 'object') {
    throw new TypeError('Expected a file save request.');
  }
  const { defaultPath, data, filters } = request as {
    defaultPath?: unknown;
    data?: unknown;
    filters?: unknown;
  };
  if (typeof defaultPath !== 'string' || (typeof data !== 'object' && !(data instanceof ArrayBuffer))) {
    throw new TypeError('Expected a file name and binary file data.');
  }
  const bytes = data instanceof Uint8Array
    ? Buffer.from(data)
    : data instanceof ArrayBuffer
      ? Buffer.from(data)
      : null;
  if (!bytes) throw new TypeError('File data must be a byte array.');
  const options = {
    defaultPath,
    filters: Array.isArray(filters) ? filters as Electron.FileFilter[] : undefined,
  };
  const result = mainWindow && !mainWindow.isDestroyed()
    ? await dialog.showSaveDialog(mainWindow, options)
    : await dialog.showSaveDialog(options);
  if (result.canceled || !result.filePath) return null;
  await writeFile(result.filePath, bytes);
  return result.filePath;
});
ipcMain.handle('print-note-pdf', async (_event, defaultPath: unknown) => {
  if (typeof defaultPath !== 'string') throw new TypeError('Expected a PDF file name.');
  if (!mainWindow || mainWindow.isDestroyed()) throw new Error('The Rudra window is not available.');
  const pdf = await mainWindow.webContents.printToPDF({
    pageSize: 'A4',
    printBackground: true,
  });
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath,
    filters: [{ name: 'PDF document', extensions: ['pdf'] }],
  });
  if (result.canceled || !result.filePath) return null;
  await writeFile(result.filePath, pdf);
  return result.filePath;
});
ipcMain.handle('open-backend-log', () => {
  if (backendLogPath) void shell.openPath(backendLogPath);
});
ipcMain.handle('open-external', (_event, url: unknown) => {
  if (typeof url !== 'string') throw new TypeError('Expected an external URL string.');
  openExternalUrl(url);
});

if (hasSingleInstanceLock) {
  app.setAppUserModelId('com.rudra.ai');
  app.whenReady().then(async () => {
    try {
      const port = await findAvailablePort(8000);
      backendConfig = {
        httpBase: `http://127.0.0.1:${port}`,
        wsUrl: `ws://127.0.0.1:${port}/ws/voice`,
        token: randomBytes(32).toString('hex'),
      };
    } catch (error) {
      console.error('[Backend] Could not reserve a local port:', error);
    }
    createWindow();
    createTray();
    globalShortcut.register('CommandOrControl+Shift+Space', toggleWindow);
    void startBackend();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });

  app.on('before-quit', () => {
    isQuitting = true;
    killBackend();
  });

  app.on('will-quit', () => {
    globalShortcut.unregisterAll();
    killBackend();
  });
}
