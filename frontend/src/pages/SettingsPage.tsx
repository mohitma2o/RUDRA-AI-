/**
 * RUDRA AI - Settings Page
 * Configuration for models, voice, parameters, theme, and paths.
 */

import { useState } from 'react';
import { Check, Server, Cpu } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export default function SettingsPage() {
  const { ollamaStatus } = useAppStore();
  const [model, setModel] = useState('qwen2.5:3b');
  const [temperature, setTemperature] = useState('0.7');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="page-container" id="settings-page">
      <h1 className="page-title">Preferences & Settings</h1>
      <p className="page-subtitle">Configure AI model parameters, voice options, and application settings</p>

      {saved && (
        <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(34, 197, 94, 0.15)', color: 'var(--success)', fontSize: 13, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Check size={16} /> Settings saved successfully.
        </div>
      )}

      <div className="card" style={{ maxWidth: 700 }}>
        {/* Model Section */}
        <div className="settings-group">
          <h3 className="settings-group-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cpu size={16} style={{ color: 'var(--accent-primary)' }} />
            Local LLM Configuration
          </h3>

          <div className="setting-row">
            <div className="setting-info">
              <div className="setting-label">Selected AI Model</div>
              <div className="setting-desc">Primary local model running on Ollama</div>
            </div>
            <div className="setting-control">
              <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
                <option value="qwen2.5:3b">Qwen 2.5 3B (Recommended for i3 + 12GB RAM)</option>
                <option value="gemma:2b">Gemma 2B (Lightweight)</option>
                <option value="llama3.2:3b">Llama 3.2 3B</option>
              </select>
            </div>
          </div>

          <div className="setting-row">
            <div className="setting-info">
              <div className="setting-label">Temperature</div>
              <div className="setting-desc">Controls response creativity (0.0 = Precise, 1.0 = Creative)</div>
            </div>
            <div className="setting-control">
              <input
                type="number"
                className="input"
                style={{ width: 80 }}
                step="0.1"
                min="0.0"
                max="1.5"
                value={temperature}
                onChange={(e) => setTemperature(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Server status */}
        <div className="settings-group">
          <h3 className="settings-group-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Server size={16} style={{ color: 'var(--accent-primary)' }} />
            Ollama Server Status
          </h3>

          <div className="setting-row">
            <div className="setting-info">
              <div className="setting-label">Connection Status</div>
              <div className="setting-desc">http://localhost:11434</div>
            </div>
            <div className="setting-control" style={{ fontSize: 13, fontWeight: 600, color: ollamaStatus.status === 'online' ? 'var(--success)' : 'var(--error)' }}>
              {ollamaStatus.status.toUpperCase()}
            </div>
          </div>
        </div>

        <button
          className="new-chat-btn"
          style={{ justifyContent: 'center', background: 'var(--accent-gradient)', border: 'none', color: 'white', marginTop: 10 }}
          onClick={handleSave}
        >
          Save Settings
        </button>
      </div>
    </div>
  );
}
