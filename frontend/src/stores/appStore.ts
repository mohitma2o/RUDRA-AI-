/**
 * RUDRA AI - Global State Store (Zustand)
 * Manages application state for chat, settings, and UI.
 */

import { create } from 'zustand';
import { api, type Message, type Conversation, type SystemStats, type OllamaStatus } from '../services/api';

type Page = 'chat' | 'system' | 'memory' | 'automation' | 'documents' | 'coding' | 'settings' | 'plugins';

interface AppState {
  // ─── UI State ───────────────────────────────────────
  currentPage: Page;
  sidebarOpen: boolean;
  setPage: (page: Page) => void;
  toggleSidebar: () => void;

  // ─── Chat State ─────────────────────────────────────
  conversations: Conversation[];
  currentConversationId: number | null;
  messages: Message[];
  isGenerating: boolean;
  streamingContent: string;

  loadConversations: () => Promise<void>;
  selectConversation: (id: number) => Promise<void>;
  startNewChat: () => void;
  deleteConversation: (id: number) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;

  // ─── Voice State ─────────────────────────────────────
  voiceEnabled: boolean;
  setVoiceEnabled: (enabled: boolean) => void;

  // ─── System State ───────────────────────────────────
  systemStats: SystemStats | null;
  loadSystemStats: () => Promise<void>;

  // ─── Ollama Status ──────────────────────────────────
  ollamaStatus: OllamaStatus;
  checkOllamaStatus: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  // ─── UI State ─────────────────────────────────────────
  currentPage: 'chat',
  sidebarOpen: true,
  setPage: (page) => set({ currentPage: page }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  // ─── Chat State ───────────────────────────────────────
  conversations: [],
  currentConversationId: null,
  messages: [],
  isGenerating: false,
  streamingContent: '',

  loadConversations: async () => {
    try {
      const conversations = await api.getConversations();
      set({ conversations });
    } catch (e) {
      console.error('Failed to load conversations:', e);
    }
  },

  selectConversation: async (id: number) => {
    try {
      const messages = await api.getConversationMessages(id);
      set({ currentConversationId: id, messages });
    } catch (e) {
      console.error('Failed to load conversation:', e);
    }
  },

  startNewChat: () => {
    set({
      currentConversationId: null,
      messages: [],
      streamingContent: '',
      currentPage: 'chat',
    });
  },

  deleteConversation: async (id: number) => {
    try {
      await api.deleteConversation(id);
      const { currentConversationId, loadConversations } = get();
      if (currentConversationId === id) {
        set({ currentConversationId: null, messages: [] });
      }
      await loadConversations();
    } catch (e) {
      console.error('Failed to delete conversation:', e);
    }
  },

  sendMessage: async (content: string) => {
    const { currentConversationId, messages } = get();

    // Add user message immediately
    const userMessage: Message = { role: 'user', content };
    set({
      messages: [...messages, userMessage],
      isGenerating: true,
      streamingContent: '',
    });

    try {
      let convId = currentConversationId;

      await api.sendMessage(
        content,
        convId,
        // onChunk
        (chunk) => {
          set((s) => ({ streamingContent: s.streamingContent + chunk }));
        },
        // onInfo
        (data) => {
          convId = data.conversation_id;
          set({ currentConversationId: data.conversation_id });
        },
        // onTitle
        (title) => {
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === convId ? { ...c, title } : c
            ),
          }));
        },
        // onDone
        () => {
          const { streamingContent, messages: currentMessages } = get();
          const assistantMessage: Message = {
            role: 'assistant',
            content: streamingContent,
          };
          set({
            messages: [...currentMessages, assistantMessage],
            isGenerating: false,
            streamingContent: '',
          });
          // Reload conversations to get new one
          get().loadConversations();
        },
      );
    } catch (e) {
      console.error('Failed to send message:', e);
      const { messages: currentMessages } = get();
      const errorMessage: Message = {
        role: 'assistant',
        content: `⚠️ Error: ${e instanceof Error ? e.message : 'Failed to connect to RUDRA AI backend. Make sure the server is running.'}`,
      };
      set({
        messages: [...currentMessages, errorMessage],
        isGenerating: false,
        streamingContent: '',
      });
    }
  },

  // ─── Voice State ─────────────────────────────────────
  voiceEnabled: typeof window !== 'undefined' ? localStorage.getItem('voiceEnabled') !== 'false' : true,
  setVoiceEnabled: (enabled: boolean) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('voiceEnabled', enabled ? 'true' : 'false');
    }
    set({ voiceEnabled: enabled });
  },

  // ─── System State ─────────────────────────────────────
  systemStats: null,
  loadSystemStats: async () => {
    try {
      const stats = await api.getSystemStats();
      set({ systemStats: stats });
    } catch (e) {
      console.error('Failed to load system stats:', e);
    }
  },

  // ─── Ollama Status ────────────────────────────────────
  ollamaStatus: { status: 'offline', message: 'Checking...' },
  checkOllamaStatus: async () => {
    try {
      const status = await api.getOllamaStatus();
      set({ ollamaStatus: status });
    } catch {
      set({ ollamaStatus: { status: 'offline', message: 'Backend not running' } });
    }
  },
}));
