/**
 * RUDRA AI - Coding Assistant Page
 * Code generator, error explainer, and project scaffolding tool.
 */

import { useState } from 'react';
import { Code2, Bug, Sparkles } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export default function CodingPage() {
  const { sendMessage, setPage } = useAppStore();
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState('python');

  const handleGenerateCode = () => {
    if (!prompt.trim()) return;
    sendMessage(`Write clean, commented ${language} code for: ${prompt}`);
    setPage('chat');
  };

  const handleExplainError = () => {
    if (!prompt.trim()) return;
    sendMessage(`Please analyze this error log/stack trace and explain how to fix it:\n\n\`\`\`\n${prompt}\n\`\`\``);
    setPage('chat');
  };

  return (
    <div className="page-container" id="coding-page">
      <h1 className="page-title">AI Coding Assistant</h1>
      <p className="page-subtitle">Generate code, debug stack traces, and build project scaffolding</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Code2 size={18} style={{ color: 'var(--accent-primary)' }} />
              Code Generator & Debugger
            </h3>

            <select
              className="select"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="python">Python</option>
              <option value="typescript">TypeScript / JavaScript</option>
              <option value="html/css">HTML & CSS</option>
              <option value="sql">SQL Query</option>
              <option value="c++">C++</option>
            </select>
          </div>

          <textarea
            className="input"
            style={{ width: '100%', minHeight: 140, marginBottom: 16, fontFamily: 'var(--font-mono)', fontSize: 13 }}
            placeholder="Describe what code you want to build or paste your error stack trace here..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="new-chat-btn"
              style={{ flex: 1, justifyContent: 'center', background: 'var(--accent-gradient)', border: 'none', color: 'white' }}
              onClick={handleGenerateCode}
            >
              <Sparkles size={16} />
              Generate {language} Code
            </button>
            <button
              className="new-chat-btn"
              style={{ flex: 1, justifyContent: 'center', borderColor: 'var(--warning)', color: 'var(--warning)' }}
              onClick={handleExplainError}
            >
              <Bug size={16} />
              Explain Error Trace
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
