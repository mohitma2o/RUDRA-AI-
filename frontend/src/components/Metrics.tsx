import React from 'react';
import { useVoiceStore } from '../store/voiceStore';
import { Zap, Activity, Cpu, Check, TriangleAlert } from 'lucide-react';

export const Metrics: React.FC = () => {
  const {
    timing, isConnected, backendStatus, llmStatus, voiceStatus, settings, systemMetrics,
  } = useVoiceStore();
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
    <div className="telemetry-panel" data-no-drag>
      <div className="telemetry-topline">
        <div className="telemetry-statuses">
          <div className="telemetry-status" title={isConnected ? 'Backend WebSocket is connected.' : backendStatus === 'failed' ? 'Backend connection failed.' : 'Connecting to the backend.'}>
            <span className={`h-1.5 w-1.5 rounded-full ${backendColor}`} />
            <span>BACKEND</span>
          </div>
          <div className="telemetry-status" title={llmReason}>
            <span className={`h-1.5 w-1.5 rounded-full ${llmColor}`} />
            <span>OLLAMA</span>
          </div>
          <div className="telemetry-status" title={voiceReason}>
            <span className={`h-1.5 w-1.5 rounded-full ${voiceColor}`} />
            <span>VOICE</span>
          </div>
        </div>

        <div className="telemetry-model" title={llmReason}>
          <Cpu className="h-3 w-3 text-cyan-300" />
          <span>{llmStatus?.model || settings.llm_model}</span>
          {llmStatus?.installed
            ? <Check className="h-2.5 w-2.5 text-emerald-400" aria-label="Model installed" />
            : llmStatus?.reachable
              ? <TriangleAlert className="h-2.5 w-2.5 text-amber-400" aria-label="Model missing" />
              : null}
        </div>
      </div>

      <div className="telemetry-grid" aria-label="Live system telemetry">
        <TelemetryBar
          label="CPU"
          value={systemMetrics?.cpu_percent}
          detail={systemMetrics ? `${Math.round(systemMetrics.cpu_percent)}%` : '—'}
        />
        <TelemetryBar
          label="RAM"
          value={systemMetrics?.memory_percent}
          detail={systemMetrics
            ? `${systemMetrics.memory_used_gb}/${systemMetrics.memory_total_gb} GB`
            : 'Waiting'}
        />
      </div>

      <div className="telemetry-latency">
        {timing.llm_first_token_ms !== undefined && (
          <div className="flex items-center gap-1" title="First token latency">
            <Zap className="h-3 w-3 text-amber-300" />
            <span>{timing.llm_first_token_ms}ms</span>
          </div>
        )}

        {timing.total_ms !== undefined && (
          <div className="flex items-center gap-1" title="Total response latency">
            <Activity className="h-3 w-3 text-cyan-300" />
            <span>{timing.total_ms}ms</span>
          </div>
        )}
      </div>
    </div>
  );
};

interface TelemetryBarProps {
  label: string;
  value?: number;
  detail: string;
}

const TelemetryBar: React.FC<TelemetryBarProps> = ({ label, value, detail }) => {
  const percentage = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="telemetry-meter" aria-label={`${label} usage ${detail}`}>
      <div className="telemetry-meter-label">
        <span>{label}</span>
        <span>{detail}</span>
      </div>
      <div className="telemetry-track">
        <div className="telemetry-fill" style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
};
