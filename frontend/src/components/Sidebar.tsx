/**
 * RUDRA AI - Sidebar Component
 * Navigation sidebar with conversation list and module navigation.
 */

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare, Cpu, Brain, Zap, FileText,
  Code2, Settings, Puzzle, Plus, Trash2, MessagesSquare
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';

const navItems = [
  { id: 'chat' as const, label: 'Chat', icon: MessageSquare },
  { id: 'system' as const, label: 'System Monitor', icon: Cpu },
  { id: 'memory' as const, label: 'Memory', icon: Brain },
  { id: 'automation' as const, label: 'Automation', icon: Zap },
  { id: 'documents' as const, label: 'Documents', icon: FileText },
  { id: 'coding' as const, label: 'Coding', icon: Code2 },
  { id: 'plugins' as const, label: 'Plugins', icon: Puzzle },
  { id: 'settings' as const, label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const {
    currentPage, setPage, conversations, currentConversationId,
    loadConversations, selectConversation, startNewChat,
    deleteConversation, ollamaStatus, checkOllamaStatus,
  } = useAppStore();

  useEffect(() => {
    loadConversations();
    checkOllamaStatus();
    const interval = setInterval(checkOllamaStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="sidebar" id="sidebar">
      {/* Logo */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">R</div>
          <div>
            <div className="sidebar-logo-text">RUDRA AI</div>
            <div className="sidebar-logo-version">Desktop Intelligence v1.0</div>
          </div>
        </div>
        <button className="new-chat-btn" onClick={startNewChat} id="new-chat-btn">
          <Plus size={16} />
          New Chat
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="nav-section-title">Modules</div>
        {navItems.map((item) => (
          <div
            key={item.id}
            className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => setPage(item.id)}
            id={`nav-${item.id}`}
          >
            <item.icon size={18} className="nav-icon" />
            {item.label}
          </div>
        ))}

        {/* Conversation History */}
        {conversations.length > 0 && (
          <>
            <div className="nav-section-title" style={{ marginTop: 12 }}>Recent Chats</div>
            <div className="conversation-list">
              <AnimatePresence>
                {conversations.slice(0, 15).map((conv) => (
                  <motion.div
                    key={conv.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
                    onClick={() => {
                      selectConversation(conv.id);
                      setPage('chat');
                    }}
                  >
                    <MessagesSquare size={14} style={{ flexShrink: 0, opacity: 0.5 }} />
                    <span className="conversation-title">{conv.title}</span>
                    <div
                      className="conversation-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.id);
                      }}
                    >
                      <Trash2 size={13} />
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </>
        )}
      </nav>

      {/* Footer - Status */}
      <div className="sidebar-footer">
        <div className="status-indicator">
          <div className={`status-dot ${ollamaStatus.status === 'online' ? 'online' : ollamaStatus.status === 'error' ? 'loading' : 'offline'}`} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
              {ollamaStatus.status === 'online' ? 'AI Online' : ollamaStatus.status === 'offline' ? 'AI Offline' : 'Checking...'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              {ollamaStatus.status === 'online'
                ? ollamaStatus.default_model || 'Connected'
                : 'Start Ollama to connect'}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
