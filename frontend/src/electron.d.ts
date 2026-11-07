export {};

declare global {
  interface Window {
    electronAPI?: {
      hideWindow: () => void;
      minimizeWindow: () => void;
      closeWindow: () => void;
      getVersion: () => Promise<string>;
      getBackendConfig: () => Promise<{
        httpBase: string;
        wsUrl: string;
        token: string;
      } | null>;
      openBackendLog: () => Promise<void>;
      openExternal: (url: string) => Promise<void>;
      onHotkeyTrigger: (callback: () => void) => () => void;
      onBackendStatus: (
        callback: (event: { status: string; message?: string }) => void
      ) => () => void;
    };
  }
}
