import React, { useState } from 'react';
import { Orb } from './Orb';
import { Transcript } from './Transcript';
import { Metrics } from './Metrics';
import { SettingsModal } from './SettingsModal';
import { useVoicePipeline } from '../hooks/useVoicePipeline';
import { useVoiceStore } from '../store/voiceStore';
import { Settings, Send, X, Minus, Sparkles, Volume2 } from 'lucide-react';

export const HUD: React.FC = () => {
  const [inputText, setInputText] = useState('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const { state, mode } = useVoiceStore();
  const { interrupt, sendTextQuery, sendConfirmResponse } = useVoicePipeline();

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    sendTextQuery(inputText.trim());
    setInputText('');
  };

  const handleCloseWindow = () => {
    // If in Electron, call window.electronAPI.hideWindow() or window.close()
    if ((window as any).electronAPI?.hideWindow) {
      (window as any).electronAPI.hideWindow();
    } else {
      window.close();
    }
  };

  const handleMinimizeWindow = () => {
    if ((window as any).electronAPI?.minimizeWindow) {
      (window as any).electronAPI.minimizeWindow();
    }
  };

  return (
    <div className="relative w-full max-w-[420px] rounded-3xl glass-panel p-5 flex flex-col gap-4 shadow-2xl border border-sky-500/20">
      {/* Window Header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-md shadow-sky-500/30">
            <Sparkles className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <span className="font-bold text-sm tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-indigo-300 to-purple-400">
              RUDRA AI
            </span>
            <span className="text-[10px] text-slate-400 ml-1.5 font-mono">v2.0</span>
          </div>
        </div>

        {/* Window action buttons */}
        <div className="flex items-center gap-1.5" data-no-drag>
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
            title="Settings"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleMinimizeWindow}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
            title="Minimize"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleCloseWindow}
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            title="Close / Hide HUD"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Orb Center */}
      <div className="flex flex-col items-center justify-center py-3">
        <Orb onOrbClick={interrupt} />
      </div>

      {/* Live Transcript & Conversation Box */}
      <Transcript onConfirm={sendConfirmResponse} />

      {/* Text Command Input Bar */}
      <form onSubmit={handleSendText} className="relative mt-2" data-no-drag>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={mode === 'wake' ? 'Say "Rudra..." or type a request' : 'Type a request...'}
          className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-3.5 pr-10 py-2.5 text-xs text-slate-100 placeholder:text-slate-500 outline-none focus:border-sky-500/60 focus:ring-1 focus:ring-sky-500/30 transition-all font-sans"
        />
        <button
          type="submit"
          className="absolute right-1.5 top-1.5 p-1.5 rounded-lg bg-sky-600/80 hover:bg-sky-500 text-white transition-colors disabled:opacity-40"
          disabled={!inputText.trim()}
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>

      {/* Metrics & Telemetry Bar */}
      <Metrics />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
