import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  hideWindow: () => ipcRenderer.send('window-hide'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  getVersion: () => ipcRenderer.invoke('get-version'),
  getBackendConfig: () => ipcRenderer.invoke('get-backend-config'),
  openBackendLog: () => ipcRenderer.invoke('open-backend-log'),
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
