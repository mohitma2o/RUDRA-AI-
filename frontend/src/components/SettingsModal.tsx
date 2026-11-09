import React, { useState } from 'react';
import { useVoiceStore, ListeningMode } from '../store/voiceStore';
import { X, Sliders, Mic, Globe, Cpu, Cloud } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { settings, updateSettings, mode, setMode, llmStatus, setLLMStatus } = useVoiceStore();
  const [geminiKey, setGeminiKey] = useState('');
  const [geminiSaved, setGeminiSaved] = useState(false);
  const [geminiSaving, setGeminiSaving] = useState(false);
  const [geminiError, setGeminiError] = useState('');

  if (!isOpen) return null;
  const installedModels = llmStatus?.models_installed ?? [];
  const hardwareProfile = llmStatus?.hardware_profile;
  const geminiConfigured = geminiSaved || llmStatus?.gemini_configured === true;

  const saveGeminiKey = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const apiKey = geminiKey.trim();
    if (!apiKey) {
      setGeminiError('Enter your Gemini API key to continue.');
      return;
    }
    if (apiKey.length < 6 || apiKey.length > 512) {
      setGeminiError('Gemini API keys must contain 6 to 512 characters.');
      return;
    }

    setGeminiSaving(true);
    setGeminiError('');
    try {
      const config = await window.electronAPI?.getBackendConfig();
      if (!config?.httpBase || !config.token) {
        throw new Error('Backend configuration unavailable.');
      }
      const response = await fetch(`${config.httpBase}/api/settings/gemini-key`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${config.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKey }),
      });
      const result = await response.json() as { detail?: string; configured?: boolean };
      if (!response.ok || !result.configured) {
        throw new Error(result.detail || `Could not save Gemini API key (HTTP ${response.status}).`);
      }
      setGeminiSaved(true);
      setGeminiKey('');
      const currentStatus = useVoiceStore.getState().llmStatus;
      setLLMStatus({
        reachable: currentStatus?.reachable ?? false,
        model: currentStatus?.model ?? settings.llm_model,
        installed: currentStatus?.installed ?? false,
        ...currentStatus,
        gemini_configured: true,
      });
    } catch (error) {
      setGeminiError(error instanceof Error ? error.message : String(error));
    } finally {
      setGeminiSaving(false);
    }
  };

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
            <option value="en">English (US)</option>
            <option value="hi">Hindi (हिन्दी)</option>
            <option value="pa">Punjabi (ਪੰਜਾਬੀ)</option>
          </select>
        </div>

        {/* Optional Gemini cloud provider */}
        <div className="flex flex-col gap-1.5 rounded-xl border border-sky-400/20 bg-sky-500/5 p-3">
          <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <Cloud className="w-3.5 h-3.5 text-sky-400" />
            Gemini Cloud Acceleration
          </label>
          {geminiConfigured ? (
            <p className="text-[10px] text-emerald-300" role="status">
              Gemini 2.5 Flash is configured. Cloud errors are shown without switching providers.
            </p>
          ) : typeof llmStatus?.gemini_configured !== 'boolean' ? (
            <p className="text-[10px] text-slate-400" role="status">
              Checking whether a Gemini API key is configured…
            </p>
          ) : (
            <>
              <p className="text-[10px] text-slate-400">
                Add a key to use Gemini for replies. Conversation text is sent to Google; without a key,
                Rudra uses local Ollama.
              </p>
              <form onSubmit={(event) => void saveGeminiKey(event)} className="flex flex-col gap-2">
                <input
                  type="password"
                  value={geminiKey}
                  onChange={(event) => setGeminiKey(event.target.value)}
                  minLength={6}
                  maxLength={512}
                  autoComplete="off"
                  placeholder="Gemini API key"
                  aria-label="Gemini API key"
                  className="bg-slate-950/70 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none focus:border-sky-400"
                />
                <button
                  type="submit"
                  disabled={geminiSaving || !geminiKey.trim()}
                  className="py-2 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 rounded-lg text-xs font-semibold"
                >
                  {geminiSaving ? 'Saving key…' : 'Save Gemini API key'}
                </button>
              </form>
              {geminiError && <p className="text-[10px] text-rose-300" role="alert">{geminiError}</p>}
            </>
          )}
        </div>

        {/* Ollama Model Selection */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-amber-400" />
            Ollama Model
          </label>
          <select
            value={settings.llm_model}
            onChange={(e) => updateSettings({ llm_model: e.target.value })}
            disabled={!llmStatus?.reachable || installedModels.length === 0}
            className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-400 font-mono"
          >
            {!installedModels.includes(settings.llm_model) && (
              <option value={settings.llm_model} disabled>
                {settings.llm_model} (not installed)
              </option>
            )}
            {installedModels.map((model) => {
              const recommended = hardwareProfile?.recommended_models.includes(model);
              return (
                <option key={model} value={model}>
                  {model}{recommended ? ' (recommended)' : ''}
                </option>
              );
            })}
          </select>
          {hardwareProfile && (
            <p className="text-[10px] text-slate-400">
              {hardwareProfile.tier.toUpperCase()} profile · {hardwareProfile.ram_gb} GB RAM
              <br />
              Recommended: {hardwareProfile.recommended_models.join(', ')}
              <br />
              {hardwareProfile.basis}
            </p>
          )}
          {!llmStatus && (
            <p className="text-[10px] text-slate-400">Loading installed Ollama models…</p>
          )}
          {llmStatus && !llmStatus.reachable && (
            <p className="text-[10px] text-amber-300">
              Ollama is unavailable; start it to load installed models.
            </p>
          )}
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
