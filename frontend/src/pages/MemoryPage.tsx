/**
 * RUDRA AI - Memory Page
 * Conversation history management, saved preferences, and long-term context.
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Search, Trash2, Clock, MessageSquare, Database } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export default function MemoryPage() {
  const { conversations, selectConversation, deleteConversation, setPage } = useAppStore();
  const [filter, setFilter] = useState('');

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="page-container" id="memory-page">
      <h1 className="page-title">Long-Term Memory & Sessions</h1>
      <p className="page-subtitle">Persistent storage of user conversations, preferences, and RAG context</p>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 24 }}>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Database size={20} style={{ color: 'var(--accent-primary)' }} />
            <div>
              <div style={{ fontSize: 20, fontWeight: 800 }}>{conversations.length}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Total Sessions Saved</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Brain size={20} style={{ color: 'var(--accent-secondary)' }} />
            <div>
              <div style={{ fontSize: 20, fontWeight: 800 }}>SQLite + Chroma</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Vector Store Status</div>
            </div>
          </div>
        </div>
      </div>

      {/* Search & Filter */}
      <div style={{ marginBottom: 20, display: 'flex', gap: 12 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: 12, color: 'var(--text-tertiary)' }} />
          <input
            type="text"
            className="input"
            style={{ width: '100%', paddingLeft: 38 }}
            placeholder="Search past conversations..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      </div>

      {/* List */}
      <div className="memory-list">
        {filteredConversations.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <MessageSquare size={24} />
            </div>
            <div className="empty-state-title">No Conversations Found</div>
            <div className="empty-state-desc">Your chat history will be automatically stored and remembered here.</div>
          </div>
        ) : (
          filteredConversations.map((conv) => (
            <motion.div
              key={conv.id}
              className="memory-item"
              whileHover={{ scale: 1.01 }}
              onClick={() => {
                selectConversation(conv.id);
                setPage('chat');
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div className="memory-item-title">{conv.title}</div>
                  <div className="memory-item-preview">
                    {conv.message_count} messages exchanged
                  </div>
                </div>

                <button
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-tertiary)',
                    cursor: 'pointer',
                    padding: 4,
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                  }}
                  title="Delete Session"
                >
                  <Trash2 size={16} />
                </button>
              </div>
              <div className="memory-item-time" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={12} />
                Updated {new Date(conv.updated_at).toLocaleString()}
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
