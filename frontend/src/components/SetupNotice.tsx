import { useCallback, useEffect, useState } from 'react';
import { useVoiceStore } from '../store/voiceStore';

interface SetupStatus {
  ollama_running: boolean;
  models_installed: string[];
  required_model: string;
  voice_model_installed: boolean;
  doc_model: string;
  doc_model_installed: boolean;
  stt_ready: boolean;
  tts_online: boolean;
  error?: string | null;
}

interface PullProgress {
  model?: string;
  status?: string;
  completed?: number;
  total?: number;
  error?: string;
}

async function getBackendConfig() {
  const config = await window.electronAPI?.getBackendConfig();
  if (!config?.httpBase || !config.token) throw new Error('Backend configuration unavailable.');
  return config;
}

export function SetupNotice() {
  const backendStatus = useVoiceStore((state) => state.backendStatus);
  const setVoiceStatus = useVoiceStore((state) => state.setVoiceStatus);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState<PullProgress | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const { httpBase, token } = await getBackendConfig();
      const response = await fetch(`${httpBase}/api/setup/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`Setup check failed (HTTP ${response.status}).`);
      const status = await response.json() as SetupStatus;
      setSetup(status);
      setVoiceStatus({
        sttReady: status.stt_ready,
        ttsOnline: status.tts_online,
        error: status.error,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setIsLoading(false);
    }
  }, [setVoiceStatus]);

  useEffect(() => {
    if (backendStatus === 'ready') void refresh();
  }, [backendStatus, refresh]);

  const installOllama = async () => {
    try {
      if (window.electronAPI) {
        await window.electronAPI.openExternal('https://ollama.com/download');
      } else {
        window.open('https://ollama.com/download', '_blank', 'noopener,noreferrer');
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const pullModel = async (model: string) => {
    setError('');
    setProgress({ model, status: 'Preparing download' });
    try {
      const { httpBase, token } = await getBackendConfig();
      const response = await fetch(`${httpBase}/api/setup/pull-model`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ model }),
      });
      if (!response.ok || !response.body) {
        throw new Error(`Model download failed (HTTP ${response.status}).`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finished = false;
      while (!finished) {
        const { value, done } = await reader.read();
        finished = done;
        buffer += decoder.decode(value, { stream: !done });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const event of events) {
          const data = event
            .split('\n')
            .find((line) => line.startsWith('data:'))
            ?.slice(5)
            .trim();
          if (!data) continue;
          const update = JSON.parse(data) as PullProgress;
          if (update.error) throw new Error(update.error);
          setProgress({ ...update, model });
        }
      }
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setProgress(null);
    }
  };

  const missingVoiceModel = Boolean(setup?.ollama_running && !setup.voice_model_installed);
  const missingDocModel = Boolean(setup?.ollama_running && !setup.doc_model_installed);
  if (!setup || (setup.ollama_running && !missingVoiceModel && !missingDocModel)) {
    return error ? <p className="text-[10px] text-rose-300" role="alert">{error}</p> : null;
  }

  const percent = progress?.total
    ? Math.min(100, Math.round(((progress.completed || 0) / progress.total) * 100))
    : 0;

  return (
    <section className="rounded-xl border border-amber-400/20 bg-amber-500/5 p-3 text-xs" aria-live="polite">
      {!setup.ollama_running ? (
        <>
          <p className="font-medium text-amber-200">Ollama is not reachable.</p>
          <p className="mt-1 text-slate-400">Install Ollama to enable local LLM replies. Settings and quick commands remain available.</p>
          <div className="mt-2 flex gap-3">
            <button onClick={() => void installOllama()} className="text-sky-300 underline">Install Ollama</button>
            <button onClick={() => void refresh()} disabled={isLoading} className="text-slate-300 underline">
              {isLoading ? 'Checking…' : 'Check again'}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="font-medium text-amber-200">Ollama model setup</p>
          {missingVoiceModel && (
            <p className="mt-1 text-slate-400">
              Voice model missing. Run <code>ollama pull {setup.required_model}</code>.
              {setup.models_installed.length > 0 && ` Installed: ${setup.models_installed.join(', ')}.`}
            </p>
          )}
          {missingDocModel && (
            <p className="mt-1 text-slate-400">
              Document model is optional. Run <code>ollama pull {setup.doc_model}</code> to enable document notes.
            </p>
          )}
          {progress ? (
            <div className="mt-2">
              <div className="flex justify-between text-slate-300">
                <span>{progress.status || `Downloading ${progress.model || 'model'}`}</span>
                {progress.total ? <span>{percent}%</span> : null}
              </div>
              <progress className="mt-1 w-full accent-sky-400" max={100} value={percent} />
            </div>
          ) : (
            <div className="mt-2 flex flex-wrap gap-3">
              {missingVoiceModel && (
                <button onClick={() => void pullModel(setup.required_model)} className="text-sky-300 underline">
                  Download voice model
                </button>
              )}
              {missingDocModel && (
                <button onClick={() => void pullModel(setup.doc_model)} className="text-sky-300 underline">
                  Download document model (~2 GB)
                </button>
              )}
            </div>
          )}
        </>
      )}
      {setup.error && <p className="mt-1 text-slate-400">{setup.error}</p>}
      {error && <p className="mt-1 text-rose-300" role="alert">{error}</p>}
      {setup.tts_online === false && (
        <p className="mt-1 text-slate-400">Online neural speech is unavailable; offline speech may be used.</p>
      )}
    </section>
  );
}
