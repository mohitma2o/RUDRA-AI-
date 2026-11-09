import React, { useEffect, useState } from 'react';
import { Orb } from './Orb';
import { Transcript } from './Transcript';
import { Metrics } from './Metrics';
import { SettingsModal } from './SettingsModal';
import { SetupNotice } from './SetupNotice';
import { DocumentsWorkspace } from './DocumentsWorkspace';
import { DailyWisdomCard } from './DailyWisdomCard';
import { useVoicePipeline } from '../hooks/useVoicePipeline';
import { useVoiceStore } from '../store/voiceStore';
import { Settings, Send, X, Minus, Sparkles, FileText, Mic, MicOff, Cloud, Monitor } from 'lucide-react';

export const HUD: React.FC = () => {
  const [inputText, setInputText] = useState('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDocumentsOpen, setIsDocumentsOpen] = useState(false);
  const {
    state, mode, backendStatus, backendMessage, backendConfigError,
    connectionDownSince, isConnected, errorNotice, setErrorNotice,
    setBackendConfigError, notesReady, setNotesReady,
    isMicMuted, setMicMuted,
    llmStatus, settings, updateSettings,
  } = useVoiceStore();
  const { interrupt, sendTextQuery, sendConfirmResponse, retryConnection } = useVoicePipeline();
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (connectionDownSince === null) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [connectionDownSince]);
  const retryVisible = Boolean(
    backendConfigError
    || backendStatus === 'failed'
    || (!isConnected && connectionDownSince !== null && now - connectionDownSince >= 10_000),
  );

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    sendTextQuery(inputText.trim());
    setInputText('');
  };

  const handleCloseWindow = () => {
    // If in Electron, call window.electronAPI.hideWindow() or window.close()
    if (window.electronAPI?.hideWindow) {
      window.electronAPI.hideWindow();
    } else {
      window.close();
    }
  };

  const handleMinimizeWindow = () => {
    if (window.electronAPI?.minimizeWindow) {
      window.electronAPI.minimizeWindow();
    }
  };

  return (
    <div className="hud-shell relative w-full max-w-[520px] max-h-[calc(100vh-24px)] overflow-y-auto rounded-[28px] p-5 flex flex-col gap-4">
      {/* Window Header */}
      <div className="flex items-center justify-between border-b border-cyan-300/15 pb-3">
        <div className="flex items-center gap-2">
          <div className="hud-brand-icon w-7 h-7 rounded-lg flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-cyan-100" />
          </div>
          <div>
            <div className="hud-wordmark">RUDRA <span>AI</span></div>
            <div className="hud-subtitle">PERSONAL INTELLIGENCE SYSTEM</div>
          </div>
        </div>

        {/* Window action buttons */}
        <div className="flex items-center gap-1.5" data-no-drag>
          <div className="flex items-center rounded-lg border border-slate-700/70 p-0.5" role="group" aria-label="Assistant engine">
            <button
              onClick={() => updateSettings({ engine_mode: 'CLOUD' })}
              disabled={!llmStatus?.gemini_configured}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-[9px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                settings.engine_mode === 'CLOUD'
                  ? 'bg-sky-400 text-slate-950 shadow-[0_0_10px_#00F0FF]'
                  : 'text-slate-400 hover:text-white'
              }`}
              title={llmStatus?.gemini_configured ? 'Use Gemini Cloud' : 'Add a Gemini API key in Settings first'}
              aria-pressed={settings.engine_mode === 'CLOUD'}
            >
              <Cloud className="h-3 w-3" />
              Cloud
            </button>
            <button
              onClick={() => updateSettings({ engine_mode: 'LOCAL' })}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-[9px] font-semibold transition-colors ${
                settings.engine_mode === 'LOCAL'
                  ? 'bg-sky-400 text-slate-950 shadow-[0_0_10px_#00F0FF]'
                  : 'text-slate-400 hover:text-white'
              }`}
              title="Use local Ollama"
              aria-pressed={settings.engine_mode === 'LOCAL'}
            >
              <Monitor className="h-3 w-3" />
              Local
            </button>
          </div>
          <button
            onClick={() => setMicMuted(!isMicMuted)}
            className={`p-1.5 rounded-lg transition-colors ${
              isMicMuted
                ? 'hud-icon-button hud-icon-button-muted'
                : 'hud-icon-button'
            }`}
            title={isMicMuted ? 'Unmute microphone' : 'Mute microphone'}
            aria-label={isMicMuted ? 'Unmute microphone' : 'Mute microphone'}
            aria-pressed={isMicMuted}
          >
            {isMicMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => setIsDocumentsOpen(true)}
            className="hud-icon-button"
            title="Documents"
            aria-label="Open document workspace"
          >
            <FileText className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="hud-icon-button"
            title="Settings"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleMinimizeWindow}
            className="hud-icon-button"
            title="Minimize"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleCloseWindow}
            className="hud-icon-button hover:!text-rose-300"
            title="Close / Hide HUD"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Orb Center */}
      <div className="relative flex flex-col items-center justify-center py-1">
        {(backendStatus !== 'ready' || !isConnected || backendConfigError) && (
          <div className="mb-3 text-center text-xs text-amber-200 font-mono" role="status">
            {backendConfigError || (backendStatus === 'failed'
              ? (backendMessage || 'Rudra could not start.')
              : !isConnected && connectionDownSince !== null
                ? 'Reconnecting…'
                : 'Starting Rudra...')}
            {retryVisible && window.electronAPI?.restartBackend && (
              <button
                onClick={() => {
                  setBackendConfigError('');
                  void retryConnection().catch((error: unknown) => {
                    setBackendConfigError(error instanceof Error ? error.message : String(error));
                  });
                }}
                className="ml-2 underline"
              >
                Retry connection
              </button>
            )}
            {backendStatus === 'failed' && window.electronAPI?.openBackendLog && (
              <button
                onClick={() => void window.electronAPI?.openBackendLog()}
                className="ml-2 underline"
              >
                View log
              </button>
            )}
          </div>
        )}
        <Orb onOrbClick={interrupt} />
      </div>

      {/* Live Transcript & Conversation Box */}
      <Transcript onConfirm={sendConfirmResponse} />
      <SetupNotice />

      {/* Text Command Input Bar */}
      <form onSubmit={handleSendText} className="relative mt-1" data-no-drag>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={mode === 'wake' ? 'Say "Rudra..." or type a request' : 'Type a request...'}
          className="hud-command-input w-full rounded-xl pl-3.5 pr-10 py-2.5 text-xs outline-none transition-all font-sans"
        />
        <button
          type="submit"
          className="hud-send-button absolute right-1.5 top-1.5 p-1.5 rounded-lg transition-colors disabled:opacity-40"
          disabled={!inputText.trim()}
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>

      {/* Metrics & Telemetry Bar */}
      <Metrics />
      <DailyWisdomCard />
      {errorNotice && (
        <div className="flex items-start justify-between gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200" role="alert">
          <span>{errorNotice.message}</span>
          <button onClick={() => setErrorNotice(null)} aria-label="Dismiss error" className="shrink-0">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      {notesReady && (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200" role="status">
          <span>Notes for {notesReady.filename} are ready.</span>
          <div className="flex shrink-0 gap-2">
            <button onClick={() => setIsDocumentsOpen(true)} className="underline">Open</button>
            <button onClick={() => setNotesReady(null)} aria-label="Dismiss notes notification">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
      <DocumentsWorkspace
        isOpen={isDocumentsOpen}
        onClose={() => setIsDocumentsOpen(false)}
      />
    </div>
  );
};
