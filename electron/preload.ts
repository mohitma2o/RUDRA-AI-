import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  hideWindow: () => ipcRenderer.send('window-hide'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  getVersion: () => ipcRenderer.invoke('get-version'),
  getBackendConfig: () => ipcRenderer.invoke('get-backend-config'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  saveFile: (request: {
    defaultPath: string;
    data: Uint8Array;
    filters?: { name: string; extensions: string[] }[];
  }) => ipcRenderer.invoke('save-file', request),
  printNotePdf: (defaultPath: string) => ipcRenderer.invoke('print-note-pdf', defaultPath),
  openBackendLog: () => ipcRenderer.invoke('open-backend-log'),
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  onHotkeyTrigger: (callback: () => void) => {
    const listener = () => callback();
    ipcRenderer.on('hotkey-trigger', listener);
    return () => ipcRenderer.removeListener('hotkey-trigger', listener);
  },
  onBackendStatus: (callback: (event: { status: string; message?: string }) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: { status: string; message?: string }) => {
      callback(payload);
    };
    ipcRenderer.on('backend-status', listener);
    return () => ipcRenderer.removeListener('backend-status', listener);
  },
});
