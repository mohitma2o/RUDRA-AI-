import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Check,
  Download,
  FileText,
  Pencil,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import { useVoiceStore } from '../store/voiceStore';

type NoteStyle = 'brief' | 'key_points' | 'detailed' | 'study' | 'flashcards' | 'action_items' | 'custom';
type NoteLanguage = 'same' | 'English' | 'Hindi' | 'Punjabi';
type ExportFormat = 'markdown' | 'docx' | 'pdf' | 'json';

interface DocumentNote {
  id: number;
  title: string;
  source_filename: string;
  summary: string;
  style: NoteStyle;
  language: NoteLanguage;
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

interface Flashcard {
  question: string;
  answer: string;
}

const ACCEPTED_FILES = '.txt,.md,.pdf,.docx,.pptx';
const STYLE_LABELS: Array<{ value: NoteStyle; label: string }> = [
  { value: 'brief', label: 'Brief summary' },
  { value: 'key_points', label: 'Key points' },
  { value: 'detailed', label: 'Detailed notes' },
  { value: 'study', label: 'Study notes (Cornell)' },
  { value: 'flashcards', label: 'Flashcards' },
  { value: 'action_items', label: 'Action items' },
  { value: 'custom', label: 'Custom instruction' },
];

async function getBackendConfig(): Promise<BackendConfig> {
  const config = await window.electronAPI?.getBackendConfig();
  if (!config?.httpBase || !config.token) throw new Error('Backend configuration unavailable.');
  return config;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string };
    if (body.detail) return body.detail;
  } catch {
    return `Request failed (HTTP ${response.status}).`;
  }
  return `Request failed (HTTP ${response.status}).`;
}

function toFlashcards(summary: string): Flashcard[] | null {
  try {
    const payload = JSON.parse(summary) as { flashcards?: unknown };
    if (!Array.isArray(payload.flashcards)) return null;
    const cards = payload.flashcards.filter(
      (card): card is Flashcard => Boolean(
        card
        && typeof card === 'object'
        && 'question' in card
        && 'answer' in card
        && typeof card.question === 'string'
        && typeof card.answer === 'string',
      ),
    );
    return cards.length === payload.flashcards.length ? cards : null;
  } catch {
    return null;
  }
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
  const [style, setStyle] = useState<NoteStyle>('brief');
  const [language, setLanguage] = useState<NoteLanguage>('same');
  const [instructions, setInstructions] = useState('');
  const [savedPath, setSavedPath] = useState('');
  const [printNote, setPrintNote] = useState<DocumentNote | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const notesReady = useVoiceStore((state) => state.notesReady);

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
  }, [isOpen, notesReady?.note_id, refreshNotes]);

  const followJob = async (
    jobId: string,
    config: BackendConfig,
    signal: AbortSignal,
  ) => {
    setJob({
      job_id: jobId,
      status: 'queued',
      progress: 0,
      message: 'Document queued.',
    });
    const eventsResponse = await fetch(
      `${config.httpBase}/api/documents/jobs/${jobId}/events`,
      { headers: authHeaders(config.token), signal },
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
  };

  const beginJob = async (start: (config: BackendConfig) => Promise<string>) => {
    if (isLoading) return;
    setError('');
    setSavedPath('');
    setIsLoading(true);
    setJob(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const config = await getBackendConfig();
      const jobId = await start(config);
      await followJob(jobId, config, controller.signal);
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const uploadDocument = async () => {
    if (!selectedFile) return;
    await beginJob(async (config) => {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('style', style);
      formData.append('language', language);
      if (instructions.trim()) formData.append('instructions', instructions.trim());
      const response = await fetch(`${config.httpBase}/api/documents/jobs`, {
        method: 'POST',
        headers: authHeaders(config.token),
        body: formData,
      });
      if (!response.ok) throw new Error(await readError(response));
      return (await response.json() as { job_id: string }).job_id;
    });
  };

  const regenerateNote = async (noteId: number) => {
    await beginJob(async (config) => {
      const response = await fetch(`${config.httpBase}/api/documents/notes/${noteId}/regenerate`, {
        method: 'POST',
        headers: { ...authHeaders(config.token), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          style,
          language,
          instructions: instructions.trim() || null,
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      return (await response.json() as { job_id: string }).job_id;
    });
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

  const exportNote = async (note: DocumentNote, format: ExportFormat) => {
    try {
      if (format === 'pdf') {
        if (!window.electronAPI?.printNotePdf) throw new Error('PDF export is available in the Rudra desktop app.');
        setPrintNote(note);
        await new Promise<void>((resolve) => {
          window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve()));
        });
        const path = await window.electronAPI.printNotePdf(`${note.title}.pdf`);
        setPrintNote(null);
        if (path) setSavedPath(path);
        return;
      }
      if (!window.electronAPI?.saveFile) throw new Error('File export is available in the Rudra desktop app.');
      const config = await getBackendConfig();
      const response = await fetch(
        `${config.httpBase}/api/documents/notes/${note.id}/export?format=${format}`,
        { headers: authHeaders(config.token) },
      );
      if (!response.ok) throw new Error(await readError(response));
      const extension = format === 'markdown' ? 'md' : format;
      const labels: Record<ExportFormat, string> = {
        markdown: 'Markdown note',
        docx: 'Word document',
        pdf: 'PDF document',
        json: 'Flashcard JSON',
      };
      const path = await window.electronAPI.saveFile({
        defaultPath: `${note.title}.${extension}`,
        data: new Uint8Array(await response.arrayBuffer()),
        filters: [{ name: labels[format], extensions: [extension] }],
      });
      if (path) setSavedPath(path);
    } catch (reason) {
      setPrintNote(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  if (!isOpen) return null;

  return (
    <>
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
                <p className="text-[11px] text-slate-400">Create summaries or notes in your chosen style.</p>
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
                  TXT, Markdown, PDF, DOCX, and PPTX files are processed locally. Uploaded copies are removed after extraction; extracted text stays in your local notes database for regeneration.
                </p>
                <label className="mt-3 flex cursor-pointer flex-col items-center rounded-lg border border-dashed border-slate-600 px-3 py-5 text-center hover:border-sky-400/70">
                  <UploadCloud className="mb-2 h-5 w-5 text-sky-300" />
                  <span className="text-xs text-slate-200">{selectedFile?.name || 'Choose a document'}</span>
                  <input
                    type="file"
                    accept={ACCEPTED_FILES}
                    className="sr-only"
                    onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                    disabled={isLoading}
                  />
                </label>

                <label className="mt-3 block text-[11px] text-slate-300">
                  Note style
                  <select
                    value={style}
                    onChange={(event) => setStyle(event.target.value as NoteStyle)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-slate-100"
                    disabled={isLoading}
                  >
                    {STYLE_LABELS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="mt-3 block text-[11px] text-slate-300">
                  Language
                  <select
                    value={language}
                    onChange={(event) => setLanguage(event.target.value as NoteLanguage)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-slate-100"
                    disabled={isLoading}
                  >
                    <option value="same">Same as document</option>
                    <option value="English">English</option>
                    <option value="Hindi">Hindi</option>
                    <option value="Punjabi">Punjabi</option>
                  </select>
                </label>
                {language === 'Punjabi' && (
                  <p className="mt-1 text-[10px] text-amber-300">Small models may be weaker in Punjabi.</p>
                )}
                {style === 'custom' && (
                  <label className="mt-3 block text-[11px] text-slate-300">
                    Custom instruction
                    <textarea
                      value={instructions}
                      onChange={(event) => setInstructions(event.target.value.slice(0, 1000))}
                      maxLength={1000}
                      rows={3}
                      placeholder="For example: explain this for a beginner"
                      className="mt-1 w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-slate-100"
                      disabled={isLoading}
                    />
                  </label>
                )}
                <button
                  onClick={() => void uploadDocument()}
                  disabled={!selectedFile || isLoading || (style === 'custom' && !instructions.trim())}
                  className="mt-3 w-full rounded-lg bg-sky-600 px-3 py-2 text-xs font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isLoading ? 'Summarizing…' : 'Create and save note'}
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
                </div>
              )}
              {savedPath && <p className="break-all text-[10px] text-emerald-300" role="status">Saved to: {savedPath}</p>}
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
                  Your generated notes will appear here.
                </p>
              ) : notes.map((note) => {
                const flashcards = note.style === 'flashcards' ? toFlashcards(note.summary) : null;
                return (
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
                          <button onClick={() => void exportNote(note, 'markdown')} className="rounded p-1 text-slate-400 hover:text-sky-300" aria-label={`Export ${note.title} as Markdown`}>
                            <Download className="h-3.5 w-3.5" />
                          </button>
                          <button onClick={() => void deleteNote(note.id)} className="rounded p-1 text-slate-400 hover:text-rose-300" aria-label={`Delete ${note.title}`}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">{note.source_filename} · {note.style.replace('_', ' ')}</p>
                    <p className="mt-2 rounded bg-amber-500/10 px-2 py-1 text-[10px] text-amber-200">
                      AI-generated, check against the source.
                    </p>
                    <div className="prose-note mt-2 max-h-40 overflow-y-auto text-[11px] leading-5 text-slate-300">
                      {flashcards ? (
                        <table className="w-full border-collapse text-left">
                          <thead><tr><th className="border border-slate-700 p-1">Question</th><th className="border border-slate-700 p-1">Answer</th></tr></thead>
                          <tbody>{flashcards.map((card, index) => (
                            <tr key={`${index}-${card.question}`}>
                              <td className="border border-slate-700 p-1">{card.question}</td>
                              <td className="border border-slate-700 p-1">{card.answer}</td>
                            </tr>
                          ))}</tbody>
                        </table>
                      ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.summary}</ReactMarkdown>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
                      <button onClick={() => void regenerateNote(note.id)} disabled={isLoading} className="text-sky-300 underline disabled:opacity-40">
                        Regenerate with selected style
                      </button>
                      <button onClick={() => void exportNote(note, 'docx')} className="text-sky-300 underline">Word</button>
                      <button onClick={() => void exportNote(note, 'pdf')} className="text-sky-300 underline">PDF</button>
                      {note.style === 'flashcards' && (
                        <button onClick={() => void exportNote(note, 'json')} className="text-sky-300 underline">JSON</button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      </div>
      <div id="print-root" aria-hidden="true">
        {printNote && (
          <article>
            <h1>{printNote.title}</h1>
            <p>Source: {printNote.source_filename}</p>
            <p>AI-generated, check against the source.</p>
            {printNote.style === 'flashcards' && toFlashcards(printNote.summary) ? (
              <table>
                <thead><tr><th>Question</th><th>Answer</th></tr></thead>
                <tbody>{toFlashcards(printNote.summary)?.map((card, index) => (
                  <tr key={`${index}-${card.question}`}><td>{card.question}</td><td>{card.answer}</td></tr>
                ))}</tbody>
              </table>
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{printNote.summary}</ReactMarkdown>
            )}
          </article>
        )}
      </div>
    </>
  );
};
