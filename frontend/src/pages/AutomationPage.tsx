/**
 * RUDRA AI - Automation Page
 * Control desktop applications, search files, take screenshots, and manage volume.
 */

import { useState } from 'react';
import { Zap, Search, Camera, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';

export default function AutomationPage() {
  const [appName, setAppName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{ name: string; path: string; size_kb: number }>>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [actionStatus, setActionStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const handleOpenApp = async (nameToOpen?: string) => {
    const name = nameToOpen || appName;
    if (!name.trim()) return;
    setActionStatus(null);
    try {
      const res = await api.openApp(name);
      setActionStatus({ type: res.status === 'success' ? 'success' : 'error', message: res.message });
    } catch (e) {
      setActionStatus({ type: 'error', message: String(e) });
    }
  };

  const handleCloseApp = async (nameToClose?: string) => {
    const name = nameToClose || appName;
    if (!name.trim()) return;
    setActionStatus(null);
    try {
      const res = await api.closeApp(name);
      setActionStatus({ type: res.status === 'success' ? 'success' : 'error', message: res.message });
    } catch (e) {
      setActionStatus({ type: 'error', message: String(e) });
    }
  };

  const handleFileSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await api.searchFiles(searchQuery);
      setSearchResults(res.results || []);
    } catch (e) {
      setActionStatus({ type: 'error', message: String(e) });
    } finally {
      setIsSearching(false);
    }
  };

  const [cameraStatus, setCameraStatus] = useState<{ type: 'success' | 'error'; message: string; path?: string; urls?: string[] } | null>(null);

  const handleScreenshot = async () => {
    try {
      const res = await api.takeScreenshot();
      if (res.status === 'success') {
        setActionStatus({ type: 'success', message: `Screenshot saved to: ${res.path}` });
      } else {
        setActionStatus({ type: 'error', message: 'Failed to capture screenshot' });
      }
    } catch (e) {
      setActionStatus({ type: 'error', message: String(e) });
    }
  };

  const handleCapturePhoto = async () => {
    try {
      const res = await api.captureCameraPhoto();
      if (res.status === 'success') {
        setCameraStatus({ type: 'success', message: `Photo captured at: ${res.path}`, path: res.path });
      } else {
        setCameraStatus({ type: 'error', message: res.message || 'Failed to capture photo' });
      }
    } catch (e) {
      setCameraStatus({ type: 'error', message: String(e) });
    }
  };

  const handleSearchPerson = async () => {
    try {
      const res = await api.searchPersonFromPhoto();
      if (res.status === 'success') {
        setCameraStatus({ type: 'success', message: res.message ?? 'Photo captured and search pages opened.', path: res.path, urls: res.search_urls });
      } else {
        setCameraStatus({ type: 'error', message: res.message || 'Failed to search person from photo' });
      }
    } catch (e) {
      setCameraStatus({ type: 'error', message: String(e) });
    }
  };

  return (
    <div className="page-container" id="automation-page">
      <h1 className="page-title">Desktop Automation & Utilities</h1>
      <p className="page-subtitle">Control application lifecycles, search your storage, and manage system actions</p>

      {actionStatus && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 10,
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            background: actionStatus.type === 'success' ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            border: `1px solid ${actionStatus.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            color: actionStatus.type === 'success' ? 'var(--success)' : 'var(--error)',
            fontSize: 13,
          }}
        >
          {actionStatus.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          {actionStatus.message}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        {/* App Control */}
        <div className="card">
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Zap size={18} style={{ color: 'var(--accent-primary)' }} />
            Application Launch & Termination
          </h3>
          <p className="card-subtitle" style={{ marginBottom: 16 }}>Launch or close local Windows applications</p>

          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <input
              type="text"
              className="input"
              style={{ flex: 1 }}
              placeholder="e.g. notepad, chrome, calculator, code..."
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="new-chat-btn"
              style={{ flex: 1, justifyContent: 'center', background: 'var(--accent-gradient)', border: 'none', color: 'white' }}
              onClick={() => handleOpenApp()}
            >
              Launch App
            </button>
            <button
              className="new-chat-btn"
              style={{ flex: 1, justifyContent: 'center', borderColor: 'var(--error)', color: 'var(--error)' }}
              onClick={() => handleCloseApp()}
            >
              Terminate
            </button>
          </div>

          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>Quick Shortcuts:</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['Notepad', 'Calculator', 'Paint', 'Explorer', 'CMD'].map((quick) => (
                <button
                  key={quick}
                  onClick={() => handleOpenApp(quick)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 6,
                    border: '1px solid var(--bg-glass-border)',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-secondary)',
                    fontSize: 11,
                    cursor: 'pointer',
                  }}
                >
                  {quick}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* System Utilities */}
        <div className="card">
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Camera size={18} style={{ color: 'var(--accent-primary)' }} />
            Quick System Utilities
          </h3>
          <p className="card-subtitle" style={{ marginBottom: 16 }}>Capture screenshots & system controls</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <button
              className="new-chat-btn"
              style={{ justifyContent: 'center' }}
              onClick={handleScreenshot}
            >
              <Camera size={16} />
              Take Fullscreen Screenshot
            </button>
            <button
              className="new-chat-btn"
              style={{ justifyContent: 'center', background: 'var(--accent-primary)', color: '#fff' }}
              onClick={handleCapturePhoto}
            >
              <Camera size={16} />
              Capture Camera Photo
            </button>
            <button
              className="new-chat-btn"
              style={{ justifyContent: 'center', background: 'var(--accent-secondary)', color: '#fff' }}
              onClick={handleSearchPerson}
            >
              <Search size={16} />
              Search Person from Photo
            </button>
          </div>

          {cameraStatus && (
            <div style={{ marginTop: 16, fontSize: 13, lineHeight: 1.5 }}>
              <div style={{ fontWeight: 600, color: cameraStatus.type === 'success' ? 'var(--success)' : 'var(--error)' }}>
                {cameraStatus.message}
              </div>
              {cameraStatus.path && (
                <div style={{ marginTop: 8, color: 'var(--text-secondary)' }}>
                  Saved file: {cameraStatus.path}
                </div>
              )}
              {cameraStatus.urls?.length ? (
                <div style={{ marginTop: 8, color: 'var(--text-secondary)' }}>
                  Image search pages opened in your browser.
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* File Search */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Search size={18} style={{ color: 'var(--accent-primary)' }} />
            Deep Local File Search
          </h3>
          <p className="card-subtitle" style={{ marginBottom: 16 }}>Search your home directory for documents, projects, or images</p>

          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <input
              type="text"
              className="input"
              style={{ flex: 1 }}
              placeholder="Search filename or extension (e.g. report.pdf, .py)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleFileSearch()}
            />
            <button
              className="send-btn"
              style={{ borderRadius: 'var(--radius-md)', width: 'auto', padding: '0 20px' }}
              onClick={handleFileSearch}
              disabled={isSearching}
            >
              {isSearching ? 'Searching...' : 'Search Files'}
            </button>
          </div>

          {searchResults.length > 0 && (
            <div style={{ maxHeight: 250, overflowY: 'auto' }}>
              <table className="process-table">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Path</th>
                    <th>Size (KB)</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResults.map((file, idx) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{file.name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-tertiary)' }}>{file.path}</td>
                      <td>{file.size_kb} KB</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
