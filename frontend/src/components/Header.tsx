/**
 * RUDRA AI - Header Component
 * Top navigation bar with title, status, and wake-word voice toggle.
 */

import { useState } from 'react';
import { Cpu, RefreshCw, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { api } from '../services/api';

export default function Header() {
  const { currentPage, setPage, checkOllamaStatus, voiceEnabled, setVoiceEnabled } = useAppStore();
  const [wakeWordActive, setWakeWordActive] = useState(true);

  const toggleWake = async () => {
    const nextState = !wakeWordActive;
    setWakeWordActive(nextState);
    try {
      await api.toggleWakeWord(nextState);
    } catch (e) {
      console.error('Failed to toggle wake word:', e);
    }
  };

  const getTitle = () => {
    switch (currentPage) {
      case 'chat': return 'AI Chat & Copilot';
      case 'system': return 'System Performance Monitor';
      case 'memory': return 'Memory & Session History';
      case 'automation': return 'Desktop & System Automation';
      case 'documents': return 'Document AI & Summarizer';
      case 'coding': return 'AI Coding Assistant';
      case 'plugins': return 'Plugin Manager';
      case 'settings': return 'Preferences & Settings';
      default: return 'RUDRA AI';
    }
  };

  return (
    <header className="header" id="app-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 className="header-title">{getTitle()}</h2>
      </div>

      <div className="header-actions">
        {/* Wake Word Listener Toggle */}
        <button
          className={`header-btn ${wakeWordActive ? 'active' : ''}`}
          title={wakeWordActive ? 'Say "Rudra" anytime to open app (Active)' : 'Wake Word Listener Disabled'}
          onClick={toggleWake}
          style={{
            color: wakeWordActive ? 'var(--accent-primary)' : 'var(--text-tertiary)',
            background: wakeWordActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
          }}
          id="wake-word-toggle-btn"
        >
          {wakeWordActive ? <Mic size={16} /> : <MicOff size={16} />}
        </button>

        <button
          className={`header-btn ${voiceEnabled ? 'active' : ''}`}
          title={voiceEnabled ? 'Voice responses enabled' : 'Voice responses disabled'}
          onClick={() => setVoiceEnabled(!voiceEnabled)}
          style={{
            color: voiceEnabled ? 'var(--accent-primary)' : 'var(--text-tertiary)',
            background: voiceEnabled ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
          }}
          id="voice-toggle-btn"
        >
          {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
        </button>

        <button
          className="header-btn"
          title="Refresh AI Connection"
          onClick={checkOllamaStatus}
          id="refresh-status-btn"
        >
          <RefreshCw size={15} />
        </button>

        <button
          className="header-btn"
          title="System Monitor Quick Access"
          onClick={() => setPage('system')}
          id="quick-system-btn"
        >
          <Cpu size={16} />
        </button>
      </div>
    </header>
  );
}
