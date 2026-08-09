/**
 * RUDRA AI - Chat Page
 * Main conversational interface with streaming responses and markdown rendering.
 */

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  Send, Bot, User, Copy, Check
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';

const quickActions = [
  {
    icon: '💬',
    title: 'Ask a Question',
    desc: 'Get answers to any question',
    prompt: 'Hello! What can you help me with?',
  },
  {
    icon: '💻',
    title: 'Write Code',
    desc: 'Generate code in any language',
    prompt: 'Write a Python function to sort a list using merge sort with comments',
  },
  {
    icon: '📄',
    title: 'Summarize Text',
    desc: 'Condense long documents',
    prompt: 'How can I summarize a PDF document?',
  },
  {
    icon: '⚡',
    title: 'Automate Tasks',
    desc: 'Control your desktop with AI',
    prompt: 'What desktop tasks can you automate for me?',
  },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      style={{
        position: 'absolute', top: 8, right: 8,
        background: 'rgba(255,255,255,0.1)', border: 'none',
        borderRadius: 6, padding: '4px 8px', cursor: 'pointer',
        color: 'var(--text-secondary)', fontSize: 11,
        display: 'flex', alignItems: 'center', gap: 4,
        transition: 'all 0.2s',
      }}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

export default function ChatPage() {
  const {
    messages, isGenerating, streamingContent,
    currentConversationId, sendMessage, voiceEnabled,
  } = useAppStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const lastSpokenIndexRef = useRef(-1);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [currentConversationId]);

  useEffect(() => {
    if (!voiceEnabled || !('speechSynthesis' in window)) {
      return;
    }

    const lastIndex = messages.length - 1;
    if (lastIndex <= lastSpokenIndexRef.current) {
      return;
    }

    const lastMessage = messages[lastIndex];
    if (lastMessage?.role === 'assistant' && lastMessage.content.trim()) {
      lastSpokenIndexRef.current = lastIndex;
      const utterance = new SpeechSynthesisUtterance(lastMessage.content.replace(/\n/g, ' '));
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    }
  }, [messages, voiceEnabled]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isGenerating) return;
    setInput('');
    await sendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickAction = (prompt: string) => {
    sendMessage(prompt);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 150) + 'px';
  };

  const showWelcome = messages.length === 0 && !isGenerating;

  return (
    <div className="chat-container" id="chat-page">
      {showWelcome ? (
        <motion.div
          className="welcome-screen"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="welcome-logo">R</div>
          <h1 className="welcome-title">Welcome to RUDRA AI</h1>
          <p className="welcome-subtitle">
            Your intelligent desktop copilot. Ask questions, write code,
            automate tasks, and more.
          </p>
          <div className="quick-actions">
            {quickActions.map((action, i) => (
              <motion.div
                key={i}
                className="quick-action"
                onClick={() => handleQuickAction(action.prompt)}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * (i + 1) }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="quick-action-icon">{action.icon}</div>
                <div className="quick-action-title">{action.title}</div>
                <div className="quick-action-desc">{action.desc}</div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      ) : (
        <div className="chat-messages" id="chat-messages">
          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                className={`message ${msg.role}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="message-avatar">
                  {msg.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
                </div>
                <div className="message-content">
                  <div className="message-bubble">
                    {msg.role === 'assistant' ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '');
                            const codeString = String(children).replace(/\n$/, '');
                            if (match) {
                              return (
                                <div style={{ position: 'relative' }}>
                                  <CopyButton text={codeString} />
                                  <SyntaxHighlighter
                                    style={vscDarkPlus as any}
                                    language={match[1]}
                                    PreTag="div"
                                    customStyle={{
                                      margin: '10px 0',
                                      borderRadius: 10,
                                      fontSize: 13,
                                      padding: '16px 14px',
                                      paddingTop: 36,
                                      background: '#0d0d14',
                                    }}
                                  >
                                    {codeString}
                                  </SyntaxHighlighter>
                                </div>
                              );
                            }
                            return <code className={className} {...props}>{children}</code>;
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isGenerating && streamingContent && (
            <motion.div
              className="message assistant"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="message-avatar">
                <Bot size={16} />
              </div>
              <div className="message-content">
                <div className="message-bubble">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const codeString = String(children).replace(/\n$/, '');
                        if (match) {
                          return (
                            <SyntaxHighlighter
                              style={vscDarkPlus as any}
                              language={match[1]}
                              PreTag="div"
                              customStyle={{
                                margin: '10px 0',
                                borderRadius: 10,
                                fontSize: 13,
                                padding: '16px 14px',
                                background: '#0d0d14',
                              }}
                            >
                              {codeString}
                            </SyntaxHighlighter>
                          );
                        }
                        return <code className={className} {...props}>{children}</code>;
                      },
                    }}
                  >
                    {streamingContent}
                  </ReactMarkdown>
                </div>
              </div>
            </motion.div>
          )}

          {isGenerating && !streamingContent && (
            <motion.div
              className="message assistant"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="message-avatar">
                <Bot size={16} />
              </div>
              <div className="message-content">
                <div className="message-bubble">
                  <div className="typing-indicator">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          <div className="chat-input-box">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Ask RUDRA AI anything..."
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isGenerating}
              id="chat-input"
            />
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!input.trim() || isGenerating}
              id="send-btn"
            >
              <Send size={16} />
            </button>
          </div>
          <div className="chat-input-hint">
            RUDRA AI uses Ollama locally • Press Enter to send, Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  );
}
