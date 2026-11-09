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
      restartBackend: () => Promise<void>;
      saveFile: (request: {
        defaultPath: string;
        data: Uint8Array;
        filters?: { name: string; extensions: string[] }[];
      }) => Promise<string | null>;
      printNotePdf: (defaultPath: string) => Promise<string | null>;
      openBackendLog: () => Promise<void>;
      openExternal: (url: string) => Promise<void>;
      onHotkeyTrigger: (callback: () => void) => () => void;
      onBackendStatus: (
        callback: (event: { status: string; message?: string }) => void
      ) => () => void;
    };
  }
}
