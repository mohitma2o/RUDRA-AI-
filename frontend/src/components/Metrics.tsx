import React from 'react';
import { useVoiceStore } from '../store/voiceStore';
import { Zap, Activity, Cpu, Check, TriangleAlert } from 'lucide-react';

export const Metrics: React.FC = () => {
  const { timing, isConnected, backendStatus, llmStatus, voiceStatus, settings } = useVoiceStore();
  const backendColor = isConnected
    ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
    : backendStatus === 'failed'
      ? 'bg-rose-500'
      : 'bg-amber-400';
  const llmColor = !llmStatus
    ? 'bg-amber-400'
    : !llmStatus.reachable
      ? 'bg-rose-500'
      : llmStatus.installed
        ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
        : 'bg-amber-400';
  const voiceColor = !voiceStatus
    ? 'bg-amber-400'
    : !voiceStatus.sttReady
      ? 'bg-rose-500'
      : voiceStatus.ttsOnline
        ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
        : 'bg-amber-400';
  const llmReason = !llmStatus
    ? 'Waiting for Ollama status.'
    : !llmStatus.reachable
      ? llmStatus.error || 'Ollama is not running.'
      : !llmStatus.installed
        ? `Model missing. Run: ollama pull ${llmStatus.model}`
        : `${llmStatus.model} is installed and Ollama is reachable.`;
  const voiceReason = !voiceStatus
    ? 'Checking speech recognition and speech synthesis.'
    : !voiceStatus.sttReady
      ? 'Speech recognition model is not ready.'
      : voiceStatus.ttsOnline
        ? 'Speech recognition is ready; online neural speech is available.'
        : 'Speech recognition is ready; online neural speech is unavailable, offline speech will be used.';

  return (
    <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-[10px] text-slate-400 font-mono select-none" data-no-drag>
      <div className="flex items-center gap-2.5">
        <div className="flex items-center gap-1" title={isConnected ? 'Backend WebSocket is connected.' : backendStatus === 'failed' ? 'Backend connection failed.' : 'Connecting to the backend.'}>
          <span className={`h-1.5 w-1.5 rounded-full ${backendColor}`} />
          <span>BACKEND</span>
        </div>
        <div className="flex items-center gap-1" title={llmReason}>
          <span className={`h-1.5 w-1.5 rounded-full ${llmColor}`} />
          <span>LLM</span>
        </div>
        <div className="flex items-center gap-1" title={voiceReason}>
          <span className={`h-1.5 w-1.5 rounded-full ${voiceColor}`} />
          <span>VOICE</span>
        </div>
      </div>

      {/* Latency telemetry */}
      <div className="flex items-center gap-3">
        {timing.llm_first_token_ms !== undefined && (
          <div className="flex items-center gap-1 text-slate-300" title="First token latency">
            <Zap className="w-3 h-3 text-amber-400" />
            <span>{timing.llm_first_token_ms}ms</span>
          </div>
        )}

        {timing.total_ms !== undefined && (
          <div className="flex items-center gap-1 text-slate-300" title="Total response latency">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span>{timing.total_ms}ms</span>
          </div>
        )}

        <div className="flex items-center gap-1 text-slate-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-slate-800" title={llmReason}>
          <Cpu className="w-2.5 h-2.5 text-indigo-400" />
          <span>{llmStatus?.model || settings.llm_model}</span>
          {llmStatus?.installed
            ? <Check className="h-2.5 w-2.5 text-emerald-400" aria-label="Model installed" />
            : llmStatus?.reachable
              ? <TriangleAlert className="h-2.5 w-2.5 text-amber-400" aria-label="Model missing" />
              : null}
        </div>
      </div>
    </div>
  );
};
