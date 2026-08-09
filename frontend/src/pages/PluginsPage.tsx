/**
 * RUDRA AI - Plugins Page
 * Plugin system manager for third-party extensions.
 */

import { useState } from 'react';
import { Puzzle } from 'lucide-react';

interface PluginItem {
  id: string;
  name: string;
  version: string;
  description: string;
  enabled: boolean;
  author: string;
}

const initialPlugins: PluginItem[] = [
  {
    id: 'weather',
    name: 'Weather & Forecast',
    version: '1.0.0',
    description: 'Fetch local weather forecast via OpenMeteo API',
    enabled: true,
    author: 'RUDRA Core',
  },
  {
    id: 'calculator',
    name: 'Scientific Math Engine',
    version: '1.2.0',
    description: 'Evaluate complex mathematical expressions and equations',
    enabled: true,
    author: 'RUDRA Core',
  },
  {
    id: 'github',
    name: 'GitHub Repository Manager',
    version: '0.9.1',
    description: 'Search GitHub repos, issues, and pull requests',
    enabled: false,
    author: 'Community',
  },
];

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginItem[]>(initialPlugins);

  const togglePlugin = (id: string) => {
    setPlugins((prev) =>
      prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p))
    );
  };

  return (
    <div className="page-container" id="plugins-page">
      <h1 className="page-title">Extensible Plugin Platform</h1>
      <p className="page-subtitle">Enable modular tools, integrations, and desktop automation extensions</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {plugins.map((plugin) => (
          <div key={plugin.id} className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{
                width: 42,
                height: 42,
                borderRadius: 'var(--radius-md)',
                background: plugin.enabled ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-tertiary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: plugin.enabled ? 'var(--accent-primary)' : 'var(--text-tertiary)',
              }}>
                <Puzzle size={20} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="card-title">{plugin.name}</span>
                  <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
                    v{plugin.version}
                  </span>
                </div>
                <div className="card-subtitle">{plugin.description} • By {plugin.author}</div>
              </div>
            </div>

            <label className="toggle">
              <input
                type="checkbox"
                checked={plugin.enabled}
                onChange={() => togglePlugin(plugin.id)}
              />
              <span className="toggle-slider" />
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
