import React from 'react';
import { useVoiceStore } from '../store/voiceStore';

interface OrbProps {
  onOrbClick: () => void;
}

export const Orb: React.FC<OrbProps> = ({ onOrbClick }) => {
  const { state, audioLevel } = useVoiceStore();

  // Dynamic scale and color palette based on state & audioLevel
  const dynamicScale = 1 + (state === 'listening' ? (audioLevel / 100) * 0.45 : 0);

  const getOrbGradient = () => {
    switch (state) {
      case 'listening':
        return 'from-cyan-400 via-teal-500 to-blue-600 shadow-cyan-500/50';
      case 'thinking':
        return 'from-violet-500 via-purple-600 to-amber-500 shadow-purple-500/50';
      case 'speaking':
        return 'from-blue-500 via-indigo-600 to-cyan-400 shadow-blue-500/50';
      case 'confirming':
        return 'from-amber-400 via-orange-500 to-rose-600 shadow-amber-500/50';
      case 'idle':
      default:
        return 'from-sky-400 via-indigo-500 to-purple-600 shadow-sky-500/30';
    }
  };

  return (
    <div
      onClick={onOrbClick}
      data-no-drag
      className="relative flex items-center justify-center cursor-pointer group w-44 h-44 select-none"
      title="Click to interrupt or speak"
    >
      {/* Outer ambient aura */}
      <div
        style={{ transform: `scale(${dynamicScale * 1.3})` }}
        className={`absolute inset-0 rounded-full bg-gradient-to-tr ${getOrbGradient()} opacity-30 blur-2xl transition-all duration-300 pointer-events-none`}
      />

      {/* Orbiting particle ring */}
      <div
        className={`absolute inset-1 rounded-full border border-sky-400/20 border-dashed animate-spin-slow pointer-events-none ${
          state === 'thinking' ? 'animate-spin' : ''
        }`}
      />

      {/* Core Orb */}
      <div
        style={{ transform: `scale(${dynamicScale})` }}
        className={`relative w-28 h-28 rounded-full bg-gradient-to-tr ${getOrbGradient()} shadow-2xl flex items-center justify-center transition-transform duration-150 ease-out`}
      >
        {/* Glass reflection highlight */}
        <div className="absolute top-2 left-4 w-10 h-6 bg-white/40 rounded-full blur-[2px] -rotate-45" />

        {/* Center state symbol or audio wave bars */}
        {state === 'speaking' ? (
          <div className="flex items-center gap-1">
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                className="w-1 bg-white/90 rounded-full animate-pulse"
                style={{
                  height: `${12 + (i % 2) * 12}px`,
                  animationDelay: `${i * 150}ms`,
                }}
              />
            ))}
          </div>
        ) : state === 'listening' ? (
          <div className="flex items-center justify-center">
            <span
              className="w-4 h-4 bg-white rounded-full shadow-[0_0_12px_#fff]"
              style={{ transform: `scale(${1 + (audioLevel / 100) * 0.8})` }}
            />
          </div>
        ) : state === 'thinking' ? (
          <div className="w-8 h-8 rounded-full border-2 border-white/80 border-t-transparent animate-spin" />
        ) : (
          <div className="w-3 h-3 bg-white/80 rounded-full shadow-[0_0_8px_rgba(255,255,255,0.8)]" />
        )}
      </div>

      {/* Spoken / State Label beneath Orb */}
      <div className="absolute -bottom-7 flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-slate-900/80 border border-slate-700/60 text-[11px] font-medium tracking-wide text-slate-300">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            state === 'listening'
              ? 'bg-cyan-400 animate-ping'
              : state === 'thinking'
              ? 'bg-purple-400 animate-pulse'
              : state === 'speaking'
              ? 'bg-blue-400'
              : 'bg-emerald-400'
          }`}
        />
        <span className="capitalize">{state}</span>
      </div>
    </div>
  );
};
