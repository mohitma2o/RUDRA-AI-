import React from 'react';
import { useVoiceStore } from '../store/voiceStore';

interface OrbProps {
  onOrbClick: () => void;
}

export const Orb: React.FC<OrbProps> = ({ onOrbClick }) => {
  const { state, audioLevel } = useVoiceStore();
  const circumference = 2 * Math.PI * 62;
  const arcProgress = Math.max(0, Math.min(100, audioLevel));

  return (
    <div
      onClick={onOrbClick}
      data-no-drag
      className={`arc-orb arc-orb-${state}`}
      title="Click to interrupt the current response"
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onOrbClick();
      }}
    >
      <div className="arc-orb-glow" />
      <svg className="arc-orb-svg" viewBox="0 0 160 160" aria-hidden="true">
        <circle className="arc-orb-track" cx="80" cy="80" r="62" />
        <circle className="arc-orb-dash" cx="80" cy="80" r="62" />
        <circle
          className="arc-orb-progress"
          cx="80"
          cy="80"
          r="62"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - arcProgress / 100)}
        />
        <circle className="arc-orb-inner-ring" cx="80" cy="80" r="48" />
      </svg>
      <div className="arc-orb-core">
        <div className="arc-orb-core-light" />
        <div className="arc-orb-bars" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((bar) => (
            <span key={bar} style={{ animationDelay: `${bar * 90}ms` }} />
          ))}
        </div>
      </div>
      <div className="arc-orb-label">
        <span className="arc-orb-indicator" />
        {state.toUpperCase()}
      </div>
    </div>
  );
};
