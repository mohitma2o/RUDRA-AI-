import React from 'react';
import { useVoiceStore } from '../store/voiceStore';
import { Zap, Activity, Cpu } from 'lucide-react';

export const Metrics: React.FC = () => {
  const { timing, isConnected, settings } = useVoiceStore();

  return (
    <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-[10px] text-slate-400 font-mono select-none" data-no-drag>
      {/* Connection indicator */}
      <div className="flex items-center gap-1.5">
        <span
          className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-rose-500 animate-pulse'
          }`}
        />
        <span>{isConnected ? 'LOCAL BACKEND' : 'OFFLINE'}</span>
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

        {/* Model badge */}
        <div className="flex items-center gap-1 text-slate-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-slate-800">
          <Cpu className="w-2.5 h-2.5 text-indigo-400" />
          <span>{settings.llm_model}</span>
        </div>
      </div>
    </div>
  );
};
