import { create } from 'zustand';

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'confirming';
export type ListeningMode = 'wake' | 'ptt' | 'handsfree';
export type BackendStatus = 'starting' | 'ready' | 'failed' | 'restarting';

export interface TimingMetrics {
  llm_first_token_ms?: number;
  tts_first_audio_ms?: number;
  total_ms?: number;
}

export interface LLMStatus {
  reachable: boolean;
  model: string;
  installed: boolean;
  error?: string | null;
  doc_model?: string;
  doc_model_installed?: boolean;
  models_installed?: string[];
  hardware_profile?: {
    tier: 'low' | 'mid' | 'high';
    ram_gb: number;
    recommended_models: string[];
    basis: string;
  };
}

export interface VoiceStatus {
  sttReady: boolean;
  ttsOnline: boolean;
  error?: string | null;
}

export interface NotesReady {
  note_id: number;
  filename: string;
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
  backendStatus: BackendStatus;
  backendMessage: string;
  backendConfigError: string;
  connectionDownSince: number | null;
  llmStatus: LLMStatus | null;
  voiceStatus: VoiceStatus | null;
  errorNotice: { code?: string; message: string } | null;
  notesReady: NotesReady | null;
  audioLevel: number;
  isMicMuted: boolean;
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
  setBackendStatus: (status: BackendStatus, message?: string) => void;
  setBackendConfigError: (message: string) => void;
  setConnectionDownSince: (timestamp: number | null) => void;
  setLLMStatus: (status: LLMStatus) => void;
  setVoiceStatus: (status: VoiceStatus) => void;
  setErrorNotice: (notice: { code?: string; message: string } | null) => void;
  setNotesReady: (notice: NotesReady | null) => void;
  setAudioLevel: (level: number) => void;
  setMicMuted: (muted: boolean) => void;
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
  backendStatus: 'starting',
  backendMessage: '',
  backendConfigError: '',
  connectionDownSince: null,
  llmStatus: null,
  voiceStatus: null,
  errorNotice: null,
  notesReady: null,
  audioLevel: 0,
  isMicMuted: false,
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
  setBackendStatus: (backendStatus, backendMessage = '') => set({ backendStatus, backendMessage }),
  setBackendConfigError: (backendConfigError) => set({ backendConfigError }),
  setConnectionDownSince: (connectionDownSince) => set({ connectionDownSince }),
  setLLMStatus: (llmStatus) => set({ llmStatus }),
  setVoiceStatus: (voiceStatus) => set({ voiceStatus }),
  setErrorNotice: (errorNotice) => set({ errorNotice }),
  setNotesReady: (notesReady) => set({ notesReady }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setMicMuted: (isMicMuted) => set({ isMicMuted }),
  setConfirmPrompt: (confirmPrompt) => set({ confirmPrompt }),
  updateSettings: (newSettings) =>
    set((s) => ({
      settings: { ...s.settings, ...newSettings },
    })),
  resetTurn: () => set({ transcript: '', reply: '', state: 'idle' }),
}));
