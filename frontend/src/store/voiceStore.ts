import { create } from 'zustand';

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'confirming';
export type ListeningMode = 'wake' | 'ptt' | 'handsfree';

export interface TimingMetrics {
  llm_first_token_ms?: number;
  tts_first_audio_ms?: number;
  total_ms?: number;
}

export interface HistoryItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  lang?: string;
  timestamp: number;
}

export interface VoiceStore {
  state: VoiceState;
  mode: ListeningMode;
  transcript: string;
  reply: string;
  currentTurn: number;
  lang: string;
  timing: TimingMetrics;
  isConnected: boolean;
  audioLevel: number;
  history: HistoryItem[];
  confirmPrompt: { tool: string; args: Record<string, any> } | null;
  settings: {
    language: string;
    voice: string;
    llm_model: string;
    stt_model: string;
  };

  setState: (state: VoiceState) => void;
  setMode: (mode: ListeningMode) => void;
  setTranscript: (text: string, lang?: string) => void;
  appendReply: (turn: number, delta: string) => void;
  setTurnEnd: (turn: number) => void;
  setTiming: (metrics: TimingMetrics) => void;
  setConnected: (connected: boolean) => void;
  setAudioLevel: (level: number) => void;
  setConfirmPrompt: (data: { tool: string; args: Record<string, any> } | null) => void;
  updateSettings: (newSettings: Partial<VoiceStore['settings']>) => void;
  resetTurn: () => void;
}

export const useVoiceStore = create<VoiceStore>((set) => ({
  state: 'idle',
  mode: 'wake',
  transcript: '',
  reply: '',
  currentTurn: 0,
  lang: 'en',
  timing: {},
  isConnected: false,
  audioLevel: 0,
  history: [],
  confirmPrompt: null,
  settings: {
    language: 'auto',
    voice: '',
    llm_model: 'qwen2.5:1.5b',
    stt_model: 'base',
  },

  setState: (state) => set({ state }),
  setMode: (mode) => set({ mode }),
  setTranscript: (text, lang) =>
    set((s) => ({
      transcript: text,
      lang: lang || s.lang,
      history: text.trim()
        ? [
            ...s.history,
            {
              id: `${Date.now()}-user`,
              role: 'user',
              content: text,
              lang: lang || s.lang,
              timestamp: Date.now(),
            },
          ]
        : s.history,
    })),
  appendReply: (turn, delta) =>
    set((s) => {
      const isNewTurn = s.currentTurn !== turn;
      const newReply = isNewTurn ? delta : s.reply + delta;
      return {
        currentTurn: turn,
        reply: newReply,
      };
    }),
  setTurnEnd: (turn) =>
    set((s) => {
      if (!s.reply.trim()) return s;
      return {
        history: [
          ...s.history,
          {
            id: `${Date.now()}-assistant`,
            role: 'assistant',
            content: s.reply.trim(),
            lang: s.lang,
            timestamp: Date.now(),
          },
        ],
      };
    }),
  setTiming: (timing) => set({ timing }),
  setConnected: (isConnected) => set({ isConnected }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setConfirmPrompt: (confirmPrompt) => set({ confirmPrompt }),
  updateSettings: (newSettings) =>
    set((s) => ({
      settings: { ...s.settings, ...newSettings },
    })),
  resetTurn: () => set({ transcript: '', reply: '', state: 'idle' }),
}));
