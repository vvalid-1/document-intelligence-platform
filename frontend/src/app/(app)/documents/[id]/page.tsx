'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { getDocument, downloadVersion, listVersions, archiveDocument, restoreDocument, favoriteDocument, unfavoriteDocument, moveDocument } from '@/lib/api/documents';
import { listFolders } from '@/lib/api/folders';
import { listSignatures } from '@/lib/api/signatures';
import { listReviews } from '@/lib/api/reviews';
import type {
  DocumentResponse,
  DocumentVersionListItem,
  FolderResponse,
  ReviewResponse,
  SignatureResponse,
} from '@/types/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ActivityTimeline, type TimelineEvent } from '@/components/ui/ActivityTimeline';
import { statusBadge } from '@/components/ui/Badge';

const POLL_INTERVAL_MS = 2000;

function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function buildTimeline(
  doc: DocumentResponse,
  reviews: ReviewResponse[],
  versions: DocumentVersionListItem[],
  sigs: SignatureResponse[],
): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  events.push({ label: 'Document uploaded', date: doc.created_at, icon: '📤' });
  if (doc.is_archived && doc.archived_at) {
    events.push({ label: 'Document archived', date: doc.archived_at, icon: '⚙' });
  }
  if (doc.status === 'ready' || doc.status === 'error') {
    events.push({
      label: doc.status === 'ready' ? 'Processing complete' : 'Processing failed',
      sublabel: doc.status === 'ready' ? `${doc.chunk_count} chunks indexed` : (doc.error_message ?? undefined),
      date: doc.updated_at,
      icon: doc.status === 'ready' ? '✅' : '❌',
    });
  }
  for (const r of reviews) {
    events.push({
      label: 'AI review completed',
      sublabel: r.overall_score != null ? `Score: ${r.overall_score}/10 · ${r.issue_count} issues` : `${r.issue_count} issues`,
      date: r.created_at, icon: '🔍',
    });
  }
  for (const v of versions) {
    const isEdit = v.agent_name === 'editor';
    const isSig = v.agent_name === 'signature';
    const isTranslation = v.agent_name === 'translator';
    const isMedia = v.agent_name === 'media_analysis';
    events.push({
      label: isEdit ? `Edit v${v.version_number} created` : isSig ? `Signature applied (v${v.version_number})` : isTranslation ? (v.change_summary ?? `Translation v${v.version_number}`) : isMedia ? 'Media analysis completed' : `Version ${v.version_number} created`,
      sublabel: isTranslation || isMedia ? undefined : (v.change_summary ?? undefined),
      date: v.created_at,
      icon: isEdit ? '✏' : isSig ? '✍' : isTranslation ? '🌐' : isMedia ? '🎙' : '📤',
    });
  }
  return events;
}

const AI_ACTIONS = [
  {
    key: 'chat',
    label: 'Chat',
    desc: 'Ask questions, get insights',
    color: 'from-blue-500/10 to-indigo-500/10 border-blue-500/20 hover:border-blue-500/40',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  {
    key: 'review',
    label: 'Review',
    desc: 'AI quality analysis & suggestions',
    color: 'from-violet-500/10 to-purple-500/10 border-violet-500/20 hover:border-violet-500/40',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
    ),
  },
  {
    key: 'edit',
    label: 'Edit',
    desc: 'Natural language editing',
    color: 'from-sky-500/10 to-blue-500/10 border-sky-500/20 hover:border-sky-500/40',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
  },
  {
    key: 'translate',
    label: 'Translate',
    desc: 'English, French, or Arabic',
    color: 'from-emerald-500/10 to-green-500/10 border-emerald-500/20 hover:border-emerald-500/40',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
      </svg>
    ),
  },
  {
    key: 'sign',
    label: 'Sign',
    desc: 'Add electronic signature',
    color: 'from-pink-500/10 to-rose-500/10 border-pink-500/20 hover:border-pink-500/40',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
      </svg>
    ),
  },
];

const MEDIA_ACTION = {
  key: 'media-analysis',
  label: 'Media Analysis',
  desc: 'Transcript, summary, action items',
  color: 'from-violet-500/10 to-purple-500/10 border-violet-500/20 hover:border-violet-500/40',
  icon: (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  ),
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [sigs, setSigs] = useState<SignatureResponse[]>([]);
  const [versions, setVersions] = useState<DocumentVersionListItem[]>([]);
  const [reviews, setReviews] = useState<ReviewResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [starring, setStarring] = useState(false);
  const [movingFolder, setMovingFolder] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPoll() {
    if (pollRef.current !== null) { clearInterval(pollRef.current); pollRef.current = null; }
  }

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [d, s, v, r, fl] = await Promise.all([getDocument(id), listSignatures(id), listVersions(id), listReviews(id), listFolders()]);
        setFolders(fl.items);
        if (cancelled) return;
        setDoc(d); setSigs(s.items); setVersions(v); setReviews(r.items);
        if (d.status === 'processing') {
          pollRef.current = setInterval(async () => {
            try {
              const updated = await getDocument(id);
              if (cancelled) return;
              setDoc(updated);
              if (updated.status !== 'processing') stopPoll();
            } catch { /* ignore */ }
          }, POLL_INTERVAL_MS);
        }
      } catch { /* ignore */ } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void init();
    return () => { cancelled = true; stopPoll(); };
  }, [id]);

  async function handleToggleArchive() {
    if (!doc || !confirm(doc.is_archived ? 'Restore this document?' : 'Archive this document?')) return;
    setArchiving(true);
    try { const u = doc.is_archived ? await restoreDocument(id) : await archiveDocument(id); setDoc(u); } catch { /* ignore */ } finally { setArchiving(false); }
  }

  async function handleMoveFolder(folderId: string | null) {
    if (!doc) return;
    setMovingFolder(true);
    try { const u = await moveDocument(id, folderId); setDoc(u); } catch { /* ignore */ } finally { setMovingFolder(false); }
  }

  async function handleToggleStar() {
    if (!doc) return;
    setStarring(true);
    try { const u = doc.is_favorite ? await unfavoriteDocument(id) : await favoriteDocument(id); setDoc(u); } catch { /* ignore */ } finally { setStarring(false); }
  }

  async function handleDownloadVersion(v: DocumentVersionListItem, fmt: 'pdf' | 'txt') {
    setDownloadingId(`${v.id}-${fmt}`);
    try { await downloadVersion(id, v.id, fmt, `v${v.version_number}_doc.${fmt}`); } catch { /* ignore */ } finally { setDownloadingId(null); }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (!doc) {
    return <div className="p-8 text-slate-500">Document not found.</div>;
  }

  const isMedia = ['audio/mpeg', 'audio/wav', 'video/mp4'].includes(doc.mime_type ?? '');
  const actions = isMedia ? [MEDIA_ACTION] : AI_ACTIONS;
  const timeline = buildTimeline(doc, reviews, versions, sigs);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <Link href="/documents">
            <Button variant="ghost" size="xs">
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Documents
            </Button>
          </Link>
        </div>

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-100">{doc.title}</h1>
              {statusBadge(doc.status)}
            </div>
            <p className="mt-0.5 text-sm text-slate-500">{doc.original_name}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={() => void handleToggleStar()}
              disabled={starring}
              className={['transition-all duration-200 p-1.5 rounded-xl', doc.is_favorite ? 'text-amber-400 bg-amber-500/10' : 'text-slate-600 hover:text-amber-400 hover:bg-amber-500/10'].join(' ')}
              title={doc.is_favorite ? 'Unstar' : 'Star'}
            >
              <svg width="16" height="16" fill={doc.is_favorite ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={doc.is_favorite ? 0 : 1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
            </button>
            <Button variant="secondary" size="sm" loading={archiving} onClick={() => void handleToggleArchive()}>
              {doc.is_archived ? 'Restore' : 'Archive'}
            </Button>
          </div>
        </div>
      </div>

      {/* Status banners */}
      {doc.is_archived && (
        <div className="mb-4 flex items-center gap-2.5 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3 text-sm text-amber-400">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} className="shrink-0">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
          </svg>
          This document is archived. Restore it to make it active again.
        </div>
      )}

      {doc.status === 'processing' && (
        <div className="mb-4 flex items-center gap-2.5 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.06] px-4 py-3 text-sm text-indigo-300">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent shrink-0" />
          <span>
            {doc.processing_step === 'ocr'
              ? 'Running OCR to extract text from image…'
              : 'Processing document — this page will update automatically.'}
          </span>
        </div>
      )}

      {doc.status === 'error' && (
        <div className="mb-4 flex items-center gap-2.5 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} className="shrink-0">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>Processing failed{doc.error_message ? `: ${doc.error_message}` : ''}</span>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main column */}
        <div className="space-y-4 lg:col-span-2">
          {/* Document info */}
          <Card>
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-slate-100">Document info</h2>
            </div>

            {folders.length > 0 && (
              <div className="mb-4 flex items-center gap-3">
                <span className="text-xs text-slate-500">Folder:</span>
                <select
                  value={doc.folder_id ?? ''}
                  disabled={movingFolder}
                  onChange={(e) => void handleMoveFolder(e.target.value || null)}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-xs text-slate-300 focus:border-indigo-500/50 focus:outline-none"
                >
                  <option value="">No folder</option>
                  {folders.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              </div>
            )}

            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {[
                ['File', doc.original_name],
                ['Type', doc.mime_type],
                ['Size', fileSize(doc.file_size_bytes)],
                ['Pages', doc.page_count ?? '—'],
                ['Chunks', doc.chunk_count],
                ['Uploaded', fmtDate(doc.created_at)],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">{k}</dt>
                  <dd className="mt-0.5 text-sm font-medium text-slate-300 break-all">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          {/* Versions */}
          {versions.length > 0 && (
            <Card>
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/10 text-sky-400">
                  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <h2 className="text-sm font-semibold text-slate-100">Versions <span className="text-slate-600">({versions.length})</span></h2>
              </div>
              <ul className="space-y-2">
                {versions.map((v) => (
                  <li key={v.id} className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.03] px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-200">
                        Version {v.version_number}
                        {v.agent_name && (
                          <span className="ml-2 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400 capitalize">
                            {v.agent_name.replace('_', ' ')}
                          </span>
                        )}
                      </p>
                      {v.change_summary && (
                        <p className="mt-0.5 truncate text-xs text-slate-500">{v.change_summary}</p>
                      )}
                      <p className="mt-0.5 text-[11px] text-slate-700">{fmtDate(v.created_at)}</p>
                    </div>
                    {(v.agent_name === 'editor' || v.agent_name === 'translator') && (
                      <div className="ml-3 flex shrink-0 gap-2">
                        <Link href={`/documents/${id}/compare?a=original&b=${v.id}`} className="text-xs text-violet-400 hover:text-violet-300 transition-colors">
                          Compare
                        </Link>
                        <button onClick={() => void handleDownloadVersion(v, 'pdf')} disabled={downloadingId !== null} className="text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-40 transition-colors">
                          {downloadingId === `${v.id}-pdf` ? '…' : 'PDF'}
                        </button>
                        <button onClick={() => void handleDownloadVersion(v, 'txt')} disabled={downloadingId !== null} className="text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-40 transition-colors">
                          {downloadingId === `${v.id}-txt` ? '…' : 'TXT'}
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Reviews */}
          {reviews.length > 0 && (
            <Card>
              <div className="mb-5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400">
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  </div>
                  <h2 className="text-sm font-semibold text-slate-100">Reviews <span className="text-slate-600">({reviews.length})</span></h2>
                </div>
                <Link href={`/documents/${id}/review`}>
                  <Button variant="glass" size="xs">New review</Button>
                </Link>
              </div>
              <ul className="space-y-2">
                {reviews.map((r) => (
                  <li key={r.id} className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.03] px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-slate-200">
                        {r.overall_score != null ? `Score: ${r.overall_score}/10` : 'Review'}
                        <span className="ml-2 text-xs font-normal text-slate-500">· {r.issue_count} issue{r.issue_count !== 1 ? 's' : ''}</span>
                      </p>
                      {r.summary && <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">{r.summary}</p>}
                    </div>
                    <span className="ml-3 shrink-0 text-xs text-slate-700">{fmtDate(r.created_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Signatures */}
          {sigs.length > 0 && (
            <Card>
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-pink-500/10 text-pink-400">
                  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </div>
                <h2 className="text-sm font-semibold text-slate-100">Signatures <span className="text-slate-600">({sigs.length})</span></h2>
              </div>
              <ul className="space-y-2">
                {sigs.map((s) => (
                  <li key={s.id} className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.03] px-4 py-3">
                    <div>
                      <p className="text-sm font-medium capitalize text-slate-200">{s.signature_type}</p>
                      <p className="text-xs text-slate-500">Page {s.page_number} · Position {s.position_data.x?.toFixed(0)}, {s.position_data.y?.toFixed(0)}{s.version_number != null ? ` · v${s.version_number}` : ''}</p>
                    </div>
                    <span className="text-xs text-slate-700">{fmtDate(s.signed_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          {/* AI Actions */}
          <Card>
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/10 text-indigo-400">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-slate-100">AI workspace</h2>
            </div>
            <div className="space-y-2">
              {actions.map(({ key, label, desc, color, icon }) => (
                <Link
                  key={key}
                  href={doc.status === 'ready' ? `/documents/${id}/${key}` : '#'}
                  className={[
                    'flex items-center gap-3 rounded-xl border bg-gradient-to-r px-3 py-3 transition-all duration-200',
                    doc.status === 'ready'
                      ? `${color} cursor-pointer`
                      : 'cursor-not-allowed border-white/[0.04] from-transparent to-transparent opacity-40',
                  ].join(' ')}
                >
                  <div className="shrink-0 text-current opacity-80">{icon}</div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">{label}</p>
                    <p className="text-xs text-slate-500">{desc}</p>
                  </div>
                  {doc.status === 'ready' && (
                    <svg className="ml-auto shrink-0 text-slate-600" width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  )}
                </Link>
              ))}
              {doc.status !== 'ready' && (
                <p className="pt-1 text-xs text-slate-700">Available once the document is ready.</p>
              )}
            </div>
          </Card>

          {/* Activity */}
          {timeline.length > 0 && (
            <Card>
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-500/10 text-slate-400">
                  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h2 className="text-sm font-semibold text-slate-100">Activity</h2>
              </div>
              <ActivityTimeline events={timeline} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
