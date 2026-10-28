import React from 'react';
import { useVoiceStore } from '../store/voiceStore';
import { AlertTriangle, Check, X } from 'lucide-react';

interface TranscriptProps {
  onConfirm: (approved: boolean) => void;
}

export const Transcript: React.FC<TranscriptProps> = ({ onConfirm }) => {
  const { transcript, reply, state, confirmPrompt } = useVoiceStore();

  return (
    <div className="w-full flex flex-col gap-3 mt-4 px-2" data-no-drag>
      {/* Confirmation alert card if Tier.CONFIRM tool requested */}
      {confirmPrompt && (
        <div className="p-3.5 rounded-xl bg-amber-500/15 border border-amber-500/40 backdrop-blur-md animate-fade-in">
          <div className="flex items-center gap-2 text-amber-300 font-medium text-xs tracking-wide">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>CONFIRMATION REQUIRED</span>
          </div>
          <p className="mt-1.5 text-xs text-slate-200">
            Allow tool <code className="text-amber-300 bg-black/40 px-1 py-0.5 rounded font-mono">{confirmPrompt.tool}</code> with parameters:
          </p>
          <pre className="mt-1 text-[11px] text-slate-400 bg-black/30 p-1.5 rounded font-mono overflow-x-auto">
            {JSON.stringify(confirmPrompt.args, null, 2)}
          </pre>
          <div className="mt-2.5 flex items-center justify-end gap-2">
            <button
              onClick={() => onConfirm(false)}
              className="flex items-center gap-1 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
            <button
              onClick={() => onConfirm(true)}
              className="flex items-center gap-1 px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium transition-colors shadow-lg shadow-amber-600/30"
            >
              <Check className="w-3.5 h-3.5" /> Approve
            </button>
          </div>
        </div>
      )}

      {/* User utterance box */}
      {transcript && (
        <div className="flex flex-col items-end">
          <div className="max-w-[85%] px-3.5 py-2 rounded-2xl rounded-tr-sm bg-gradient-to-r from-sky-600/80 to-blue-600/80 border border-sky-400/30 text-white text-xs leading-relaxed shadow-lg">
            {transcript}
          </div>
        </div>
      )}

      {/* Assistant reply box (streaming live) */}
      {(reply || state === 'thinking') && (
        <div className="flex flex-col items-start">
          <div className="max-w-[88%] px-3.5 py-2.5 rounded-2xl rounded-tl-sm bg-slate-900/90 border border-slate-700/60 text-slate-100 text-xs leading-relaxed shadow-xl">
            {reply ? (
              <span>{reply}</span>
            ) : (
              <span className="flex items-center gap-1.5 text-slate-400 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping" />
                Thinking...
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
