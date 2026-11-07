import React, { useEffect } from 'react';
import { HUD } from './components/HUD';
import { useVoiceStore } from './store/voiceStore';

export function App() {
  const setBackendStatus = useVoiceStore((state) => state.setBackendStatus);

  useEffect(() => {
    return window.electronAPI?.onBackendStatus(({ status, message }) => {
      if (status === 'starting' || status === 'ready' || status === 'failed' || status === 'restarting') {
        setBackendStatus(status, message);
      }
    });
  }, [setBackendStatus]);

  return (
    <div className="w-screen h-screen flex items-center justify-center p-4 bg-transparent">
      <HUD />
    </div>
  );
}

export default App;
