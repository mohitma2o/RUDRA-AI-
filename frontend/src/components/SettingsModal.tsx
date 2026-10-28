import React from 'react';
import { useVoiceStore, ListeningMode } from '../store/voiceStore';
import { X, Sliders, Mic, Globe, Cpu } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { settings, updateSettings, mode, setMode } = useVoiceStore();

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      data-no-drag
    >
      <div className="w-full max-w-sm rounded-2xl glass-panel p-5 text-slate-100 flex flex-col gap-4 border border-slate-700/80 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 font-semibold text-sm text-sky-400">
            <Sliders className="w-4 h-4" />
            <span>Assistant Configuration</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Input Mode */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <Mic className="w-3.5 h-3.5 text-cyan-400" />
            Activation Mode
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(['wake', 'ptt', 'handsfree'] as ListeningMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`py-1.5 text-xs font-medium rounded-xl border transition-all ${
                  mode === m
                    ? 'bg-sky-500/20 border-sky-400 text-sky-300 shadow-md shadow-sky-500/20'
                    : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:bg-slate-800'
                }`}
              >
                {m === 'wake' ? 'Wake Word' : m === 'ptt' ? 'Push to Talk' : 'Hands Free'}
              </button>
            ))}
          </div>
        </div>

        {/* Language Selection */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-indigo-400" />
            Language Mode
          </label>
          <select
            value={settings.language}
            onChange={(e) => updateSettings({ language: e.target.value })}
            className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-400"
          >
            <option value="auto">Auto-detect (EN / HI / PA)</option>
            <option value="en">English (India)</option>
            <option value="hi">Hindi (हिन्दी)</option>
            <option value="pa">Punjabi (ਪੰਜਾਬੀ)</option>
          </select>
        </div>

        {/* Ollama Model Selection */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-amber-400" />
            Ollama Model (i3 Optimized)
          </label>
          <select
            value={settings.llm_model}
            onChange={(e) => updateSettings({ llm_model: e.target.value })}
            className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-400 font-mono"
          >
            <option value="qwen2.5:1.5b">qwen2.5:1.5b (Ultra fast, recommended for i3)</option>
            <option value="qwen2.5:3b-instruct-q4_K_M">qwen2.5:3b (Standard instructed)</option>
            <option value="phi3:mini">phi3:mini (Microsoft)</option>
          </select>
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="mt-2 w-full py-2 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-sky-500/25 transition-all"
        >
          Save & Apply
        </button>
      </div>
    </div>
  );
};
