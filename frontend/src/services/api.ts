/**
 * RUDRA AI - API Service
 * Handles all communication with the FastAPI backend.
 */

const API_BASE = 'http://127.0.0.1:8000';

export interface Message {
  id?: number;
  conversation_id?: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface Conversation {
  id: number;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface SystemStats {
  cpu: {
    percent: number;
    count: number;
    frequency_mhz: number | null;
    per_core: number[];
  };
  memory: {
    total_gb: number;
    used_gb: number;
    available_gb: number;
    percent: number;
  };
  disk: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent: number;
    partitions: Array<{
      device: string;
      mountpoint: string;
      total_gb: number;
      used_gb: number;
      percent: number;
    }>;
  };
  battery: {
    percent: number | null;
    plugged: boolean | null;
    time_left: string | null;
  } | null;
  network: {
    bytes_sent: number;
    bytes_recv: number;
  };
  uptime_hours: number;
  top_processes: Array<{
    pid: number;
    name: string;
    cpu_percent: number;
    memory_percent: number;
    status: string;
  }>;
}

export interface OllamaStatus {
  status: 'online' | 'offline' | 'error';
  models?: string[];
  default_model?: string;
  has_default?: boolean;
  message?: string;
}

class ApiService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE;
  }

  // ─── Health ────────────────────────────────────────────────

  async healthCheck(): Promise<{ backend: string; ollama: OllamaStatus }> {
    const res = await fetch(`${this.baseUrl}/api/health`);
    return res.json();
  }

  async getOllamaStatus(): Promise<OllamaStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/api/chat/status`);
      return res.json();
    } catch {
      return { status: 'offline', message: 'Backend not running' };
    }
  }

  // ─── Chat ─────────────────────────────────────────────────

  async sendMessage(
    message: string,
    conversationId: number | null,
    onChunk: (chunk: string) => void,
    onInfo: (data: { conversation_id: number }) => void,
    onTitle: (title: string) => void,
    onDone: (messageId: number) => void,
  ): Promise<void> {
    const res = await fetch(`${this.baseUrl}/api/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        stream: true,
      }),
    });

    if (!res.ok) {
      throw new Error(`Chat error: ${res.statusText}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            switch (data.type) {
              case 'chunk':
                onChunk(data.content);
                break;
              case 'info':
                onInfo(data);
                break;
              case 'title':
                onTitle(data.title);
                break;
              case 'done':
                onDone(data.message_id);
                break;
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  }

  async getConversations(): Promise<Conversation[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/chat/conversations`);
      const data = await res.json();
      return data.conversations || [];
    } catch {
      return [];
    }
  }

  async getConversationMessages(conversationId: number): Promise<Message[]> {
    const res = await fetch(`${this.baseUrl}/api/chat/conversations/${conversationId}`);
    const data = await res.json();
    return data.messages || [];
  }

  async deleteConversation(conversationId: number): Promise<void> {
    await fetch(`${this.baseUrl}/api/chat/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  }

  // ─── System Monitor & Wake Word ────────────────────────────

  async getSystemStats(): Promise<SystemStats> {
    const res = await fetch(`${this.baseUrl}/api/system/stats`);
    return res.json();
  }

  connectSystemStream(onStats: (stats: SystemStats) => void): WebSocket {
    const ws = new WebSocket('ws://127.0.0.1:8000/api/system/stream');
    ws.onmessage = (event) => {
      try {
        const stats = JSON.parse(event.data);
        onStats(stats);
      } catch {
        // Skip parse errors
      }
    };
    return ws;
  }

  async toggleWakeWord(enabled: boolean): Promise<{ status: string; message: string }> {
    const res = await fetch(`${this.baseUrl}/api/system/wake-word/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    return res.json();
  }

  async triggerWakeWordManual(): Promise<{ status: string; message: string }> {
    const res = await fetch(`${this.baseUrl}/api/system/wake-word/trigger`, {
      method: 'POST',
    });
    return res.json();
  }

  // ─── Automation ───────────────────────────────────────────

  async openApp(name: string): Promise<{ status: string; message: string }> {
    const res = await fetch(`${this.baseUrl}/api/automation/app/open`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    return res.json();
  }

  async closeApp(name: string): Promise<{ status: string; message: string }> {
    const res = await fetch(`${this.baseUrl}/api/automation/app/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    return res.json();
  }

  async searchFiles(query: string, directory?: string): Promise<{
    status: string;
    count: number;
    results: Array<{ name: string; path: string; size_kb: number }>;
  }> {
    const res = await fetch(`${this.baseUrl}/api/automation/file/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, directory }),
    });
    return res.json();
  }

  async takeScreenshot(): Promise<{ status: string; path?: string }> {
    const res = await fetch(`${this.baseUrl}/api/automation/system/screenshot`, {
      method: 'POST',
    });
    return res.json();
  }

  async captureCameraPhoto(filename?: string): Promise<{ status: string; path?: string; message?: string }> {
    const res = await fetch(`${this.baseUrl}/api/automation/camera/photo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    return res.json();
  }

  async searchPersonFromPhoto(filename?: string): Promise<{ status: string; path?: string; message?: string; search_urls?: string[] }> {
    const res = await fetch(`${this.baseUrl}/api/automation/camera/search-person`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    return res.json();
  }
}

export const api = new ApiService();
