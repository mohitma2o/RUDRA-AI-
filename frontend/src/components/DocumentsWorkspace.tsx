import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Check,
  Download,
  FileText,
  Pencil,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';

interface DocumentNote {
  id: number;
  title: string;
  source_filename: string;
  summary: string;
  created_at: string;
  updated_at: string;
}

interface JobProgress {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  error?: string;
}

interface BackendConfig {
  httpBase: string;
  token: string;
}

const FALLBACK_HTTP_BASE = 'http://127.0.0.1:8000';
const ACCEPTED_FILES = '.txt,.md,.pdf,.docx,.pptx';

async function getBackendConfig(): Promise<BackendConfig> {
  const config = await window.electronAPI?.getBackendConfig();
  return {
    httpBase: config?.httpBase || FALLBACK_HTTP_BASE,
    token: config?.token || '',
  };
}

function authHeaders(token: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string };
    if (body.detail) return body.detail;
  } catch {
    // Use the status message when the server does not return JSON.
  }
  return `Request failed (HTTP ${response.status}).`;
}

export interface DocumentsWorkspaceProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentsWorkspace: React.FC<DocumentsWorkspaceProps> = ({ isOpen, onClose }) => {
  const [notes, setNotes] = useState<DocumentNote[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [job, setJob] = useState<JobProgress | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  const refreshNotes = useCallback(async () => {
    const config = await getBackendConfig();
    const response = await fetch(`${config.httpBase}/api/documents/notes`, {
      headers: authHeaders(config.token),
    });
    if (!response.ok) throw new Error(await readError(response));
    const result = await response.json() as { notes: DocumentNote[] };
    setNotes(result.notes);
  }, []);

  useEffect(() => {
    if (!isOpen) return undefined;
    let active = true;
    void refreshNotes().catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => {
      active = false;
      abortRef.current?.abort();
    };
  }, [isOpen, refreshNotes]);

  const uploadDocument = async () => {
    if (!selectedFile || isLoading) return;
    setError('');
    setIsLoading(true);
    setJob(null);
    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      const config = await getBackendConfig();
      const formData = new FormData();
      formData.append('file', selectedFile);
      const response = await fetch(`${config.httpBase}/api/documents/jobs`, {
        method: 'POST',
        headers: authHeaders(config.token),
        body: formData,
        signal: abortController.signal,
      });
      if (!response.ok) throw new Error(await readError(response));
      const created = await response.json() as { job_id: string };
      setJob({
        job_id: created.job_id,
        status: 'queued',
        progress: 0,
        message: 'Document queued.',
      });

      const eventsResponse = await fetch(
        `${config.httpBase}/api/documents/jobs/${created.job_id}/events`,
        {
          headers: authHeaders(config.token),
          signal: abortController.signal,
        },
      );
      if (!eventsResponse.ok || !eventsResponse.body) {
        throw new Error(eventsResponse.ok
          ? 'Progress stream is unavailable.'
          : await readError(eventsResponse));
      }

      const reader = eventsResponse.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finished = false;
      while (!finished) {
        const result = await reader.read();
        finished = result.done;
        buffer += decoder.decode(result.value, { stream: !finished });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const event of events) {
          const data = event
            .split('\n')
            .find((line) => line.startsWith('data:'))
            ?.slice(5)
            .trim();
          if (!data) continue;
          const update = JSON.parse(data) as JobProgress;
          setJob(update);
          if (update.status === 'failed') throw new Error(update.error || update.message);
        }
      }
      await refreshNotes();
      setSelectedFile(null);
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const cancelJob = async () => {
    if (!job || !isLoading) return;
    try {
      const config = await getBackendConfig();
      const response = await fetch(`${config.httpBase}/api/documents/jobs/${job.job_id}`, {
        method: 'DELETE',
        headers: authHeaders(config.token),
      });
      if (!response.ok) throw new Error(await readError(response));
      abortRef.current?.abort();
      setJob({ ...job, status: 'cancelled', message: 'Cancellation requested.' });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const saveTitle = async (noteId: number) => {
    try {
      const config = await getBackendConfig();
      const response = await fetch(`${config.httpBase}/api/documents/notes/${noteId}`, {
        method: 'PATCH',
        headers: { ...authHeaders(config.token), 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setEditingId(null);
      await refreshNotes();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const deleteNote = async (noteId: number) => {
    try {
      const config = await getBackendConfig();
      const response = await fetch(`${config.httpBase}/api/documents/notes/${noteId}`, {
        method: 'DELETE',
        headers: authHeaders(config.token),
      });
      if (!response.ok) throw new Error(await readError(response));
      setNotes((current) => current.filter((note) => note.id !== noteId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const exportNote = async (noteId: number) => {
    try {
      const config = await getBackendConfig();
      const response = await fetch(
        `${config.httpBase}/api/documents/notes/${noteId}/export?format=markdown`,
        { headers: authHeaders(config.token) },
      );
      if (!response.ok) throw new Error(await readError(response));
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]
        || 'rudra-note.md';
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 p-4" data-no-drag>
      <section
        className="glass-panel flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-sky-500/20"
        role="dialog"
        aria-modal="true"
        aria-labelledby="documents-title"
      >
        <header className="flex items-center justify-between border-b border-slate-700/70 px-5 py-4">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-sky-300" />
            <div>
              <h2 id="documents-title" className="text-sm font-semibold text-slate-100">Document workspace</h2>
              <p className="text-[11px] text-slate-400">Create concise summaries and keep them as notes.</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white" aria-label="Close documents">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid min-h-0 gap-4 overflow-y-auto p-5 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-700 bg-slate-950/40 p-4">
              <h3 className="text-xs font-semibold text-slate-200">Summarize a document</h3>
              <p className="mt-1 text-[11px] leading-5 text-slate-400">
                TXT, Markdown, PDF, DOCX, and PPTX files up to 25 MB are processed locally.
              </p>
              <label className="mt-3 flex cursor-pointer flex-col items-center rounded-lg border border-dashed border-slate-600 px-3 py-5 text-center hover:border-sky-400/70">
                <UploadCloud className="mb-2 h-5 w-5 text-sky-300" />
                <span className="text-xs text-slate-200">{selectedFile?.name || 'Choose a document'}</span>
                <span className="mt-1 text-[10px] text-slate-500">The document is removed after processing.</span>
                <input
                  type="file"
                  accept={ACCEPTED_FILES}
                  className="sr-only"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                  disabled={isLoading}
                />
              </label>
              <button
                onClick={() => void uploadDocument()}
                disabled={!selectedFile || isLoading}
                className="mt-3 w-full rounded-lg bg-sky-600 px-3 py-2 text-xs font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isLoading ? 'Summarizing…' : 'Summarize and save'}
              </button>
            </div>

            {job && (
              <div className="rounded-xl border border-slate-700 bg-slate-950/40 p-4" aria-live="polite">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-slate-200">{job.message}</span>
                  {isLoading && (
                    <button onClick={() => void cancelJob()} className="text-[10px] text-rose-300 underline">
                      Cancel
                    </button>
                  )}
                </div>
                <progress className="mt-3 w-full accent-sky-400" max={100} value={job.progress} />
                {job.status === 'completed' && <p className="mt-2 text-[10px] text-emerald-300">Saved to your notes.</p>}
              </div>
            )}
            {error && <p className="text-xs text-rose-300" role="alert">{error}</p>}
          </div>

          <div className="min-h-48 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-200">Saved notes</h3>
              <button onClick={() => void refreshNotes().catch((reason: unknown) => setError(String(reason)))} className="text-[10px] text-sky-300 underline">
                Refresh
              </button>
            </div>
            {notes.length === 0 ? (
              <p className="rounded-xl border border-slate-800 bg-slate-950/30 p-4 text-xs text-slate-500">
                Your summaries will appear here.
              </p>
            ) : notes.map((note) => (
              <article key={note.id} className="rounded-xl border border-slate-700/80 bg-slate-950/40 p-3">
                <div className="flex items-start gap-2">
                  {editingId === note.id ? (
                    <div className="flex min-w-0 flex-1 gap-1">
                      <input
                        value={editTitle}
                        onChange={(event) => setEditTitle(event.target.value)}
                        maxLength={200}
                        className="min-w-0 flex-1 rounded bg-slate-900 px-2 py-1 text-xs text-slate-100"
                        aria-label="Note title"
                      />
                      <button onClick={() => void saveTitle(note.id)} className="p-1 text-emerald-300" aria-label="Save title">
                        <Check className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : (
                    <h4 className="min-w-0 flex-1 truncate text-xs font-medium text-slate-100">{note.title}</h4>
                  )}
                  {editingId !== note.id && (
                    <div className="flex shrink-0 gap-1">
                      <button
                        onClick={() => {
                          setEditingId(note.id);
                          setEditTitle(note.title);
                        }}
                        className="rounded p-1 text-slate-400 hover:text-white"
                        aria-label={`Rename ${note.title}`}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => void exportNote(note.id)} className="rounded p-1 text-slate-400 hover:text-sky-300" aria-label={`Export ${note.title}`}>
                        <Download className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => void deleteNote(note.id)} className="rounded p-1 text-slate-400 hover:text-rose-300" aria-label={`Delete ${note.title}`}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
                <p className="mt-1 text-[10px] text-slate-500">{note.source_filename}</p>
                <p className="mt-2 whitespace-pre-wrap text-[11px] leading-5 text-slate-300">{note.summary}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};
