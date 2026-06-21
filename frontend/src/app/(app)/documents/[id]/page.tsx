'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { getDocument, downloadVersion, listVersions } from '@/lib/api/documents';
import { listSignatures } from '@/lib/api/signatures';
import { listReviews } from '@/lib/api/reviews';
import type {
  DocumentResponse,
  DocumentVersionListItem,
  ReviewResponse,
  SignatureResponse,
} from '@/types/api';
import { Card, CardHeader } from '@/components/ui/Card';
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
  return new Date(s).toLocaleString();
}

function buildTimeline(
  doc: DocumentResponse,
  reviews: ReviewResponse[],
  versions: DocumentVersionListItem[],
  sigs: SignatureResponse[],
): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  events.push({ label: 'Document uploaded', date: doc.created_at, icon: '📄' });

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
      date: r.created_at,
      icon: '🔍',
    });
  }

  for (const v of versions) {
    const isEdit = v.agent_name === 'editor';
    const isSig = v.agent_name === 'signature';
    const isTranslation = v.agent_name === 'translator';
    events.push({
      label: isEdit
        ? `Edit v${v.version_number} created`
        : isSig
        ? `Signature applied (v${v.version_number})`
        : isTranslation
        ? (v.change_summary ?? `Translation v${v.version_number}`)
        : `Version ${v.version_number} created`,
      sublabel: isTranslation ? undefined : (v.change_summary ?? undefined),
      date: v.created_at,
      icon: isEdit ? '✏️' : isSig ? '✍️' : isTranslation ? '🌐' : '📋',
    });
  }

  return events;
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [sigs, setSigs] = useState<SignatureResponse[]>([]);
  const [versions, setVersions] = useState<DocumentVersionListItem[]>([]);
  const [reviews, setReviews] = useState<ReviewResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPoll() {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const [d, s, v, r] = await Promise.all([
          getDocument(id),
          listSignatures(id),
          listVersions(id),
          listReviews(id),
        ]);
        if (cancelled) return;
        setDoc(d);
        setSigs(s.items);
        setVersions(v);
        setReviews(r.items);

        if (d.status === 'processing') {
          pollRef.current = setInterval(async () => {
            try {
              const updated = await getDocument(id);
              if (cancelled) return;
              setDoc(updated);
              if (updated.status !== 'processing') stopPoll();
            } catch {
              // ignore transient errors
            }
          }, POLL_INTERVAL_MS);
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void init();
    return () => {
      cancelled = true;
      stopPoll();
    };
  }, [id]);

  async function handleDownloadVersion(v: DocumentVersionListItem, fmt: 'pdf' | 'txt') {
    setDownloadingId(`${v.id}-${fmt}`);
    try {
      await downloadVersion(id, v.id, fmt, `v${v.version_number}_doc.${fmt}`);
    } catch {
      // ignore — download errors are non-critical
    } finally {
      setDownloadingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!doc) {
    return <div className="p-8 text-gray-500">Document not found.</div>;
  }

  const actions = [
    { href: `/documents/${id}/chat`, label: 'Chat', desc: 'Ask questions about this document' },
    { href: `/documents/${id}/review`, label: 'Review', desc: 'AI quality review and suggestions' },
    { href: `/documents/${id}/edit`, label: 'Edit', desc: 'Natural language editing' },
    { href: `/documents/${id}/translate`, label: 'Translate', desc: 'Translate to English, French, or Arabic' },
    { href: `/documents/${id}/sign`, label: 'Sign', desc: 'Add electronic signature' },
  ];

  const timeline = buildTimeline(doc, reviews, versions, sigs);

  return (
    <div className="p-8">
      <div className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">{doc.title}</h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">{doc.original_name}</p>
        </div>
        {statusBadge(doc.status)}
      </div>

      <div className="mb-6 flex gap-2">
        <Link href="/documents">
          <Button variant="ghost" size="sm">← Back</Button>
        </Link>
      </div>

      {doc.status === 'processing' && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          Processing document — this page will update automatically.
        </div>
      )}

      {doc.status === 'error' && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p className="font-medium">Processing failed</p>
          {doc.error_message && <p className="mt-1 text-xs">{doc.error_message}</p>}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-4 lg:col-span-2">

          {/* Document info */}
          <Card>
            <CardHeader title="Document info" />
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {[
                ['File name', doc.original_name],
                ['Type', doc.mime_type],
                ['Size', fileSize(doc.file_size_bytes)],
                ['Pages', doc.page_count ?? '—'],
                ['Chunks', doc.chunk_count],
                ['Uploaded', fmtDate(doc.created_at)],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt className="text-gray-500 dark:text-slate-400">{k}</dt>
                  <dd className="font-medium text-gray-900 dark:text-slate-100">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          {/* Versions */}
          {versions.length > 0 && (
            <Card>
              <CardHeader
                title="Versions"
                subtitle={`${versions.length} version${versions.length !== 1 ? 's' : ''}`}
              />
              <ul className="space-y-2">
                {versions.map((v) => (
                  <li
                    key={v.id}
                    className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2.5 text-sm dark:bg-slate-700"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 dark:text-slate-100">
                        Version {v.version_number}
                        {v.agent_name && (
                          <span className="ml-2 text-xs font-normal capitalize text-gray-500 dark:text-slate-400">
                            ({v.agent_name})
                          </span>
                        )}
                      </p>
                      {v.change_summary && (
                        <p className="truncate text-xs text-gray-500 dark:text-slate-400">{v.change_summary}</p>
                      )}
                      <p className="text-xs text-gray-400 dark:text-slate-500">{fmtDate(v.created_at)}</p>
                    </div>
                    {(v.agent_name === 'editor' || v.agent_name === 'translator') && (
                      <div className="ml-3 flex shrink-0 gap-2">
                        <button
                          onClick={() => void handleDownloadVersion(v, 'pdf')}
                          disabled={downloadingId !== null}
                          className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                        >
                          {downloadingId === `${v.id}-pdf` ? '…' : 'PDF'}
                        </button>
                        <button
                          onClick={() => void handleDownloadVersion(v, 'txt')}
                          disabled={downloadingId !== null}
                          className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                        >
                          {downloadingId === `${v.id}-txt` ? '…' : 'TXT'}
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Past Reviews */}
          {reviews.length > 0 && (
            <Card>
              <CardHeader
                title="Reviews"
                subtitle={`${reviews.length} review${reviews.length !== 1 ? 's' : ''}`}
              />
              <ul className="space-y-2">
                {reviews.map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2.5 text-sm dark:bg-slate-700"
                  >
                    <div>
                      <p className="font-medium text-gray-900 dark:text-slate-100">
                        {r.overall_score != null ? `Score: ${r.overall_score}/10` : 'Review'}
                        <span className="ml-2 text-xs font-normal text-gray-500 dark:text-slate-400">
                          · {r.issue_count} issue{r.issue_count !== 1 ? 's' : ''}
                        </span>
                      </p>
                      {r.summary && (
                        <p className="mt-0.5 line-clamp-1 text-xs text-gray-500 dark:text-slate-400">{r.summary}</p>
                      )}
                    </div>
                    <span className="ml-3 shrink-0 text-xs text-gray-400 dark:text-slate-500">{fmtDate(r.created_at)}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-3">
                <Link href={`/documents/${id}/review`}>
                  <Button variant="secondary" size="sm">Run new review</Button>
                </Link>
              </div>
            </Card>
          )}

          {/* Signatures */}
          {sigs.length > 0 && (
            <Card>
              <CardHeader
                title="Signatures"
                subtitle={`${sigs.length} signature${sigs.length !== 1 ? 's' : ''}`}
              />
              <ul className="space-y-2">
                {sigs.map((s) => (
                  <li key={s.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm dark:bg-slate-700">
                    <div>
                      <p className="font-medium capitalize dark:text-slate-100">{s.signature_type}</p>
                      <p className="text-xs text-gray-500 dark:text-slate-400">
                        Page {s.page_number} · x={s.position_data.x?.toFixed(0)}, y={s.position_data.y?.toFixed(0)}
                        {s.version_number != null && ` · v${s.version_number}`}
                      </p>
                    </div>
                    <span className="text-xs text-gray-400 dark:text-slate-500">{fmtDate(s.signed_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* AI Actions */}
          <Card>
            <CardHeader title="AI actions" />
            <div className="space-y-2">
              {actions.map(({ href, label, desc }) => (
                <Link
                  key={href}
                  href={doc.status === 'ready' ? href : '#'}
                  className={`block rounded-lg border border-gray-200 p-3 transition-colors dark:border-slate-700 ${doc.status === 'ready' ? 'hover:border-blue-300 hover:bg-blue-50 dark:hover:border-blue-500 dark:hover:bg-blue-900/20' : 'cursor-not-allowed opacity-50'}`}
                >
                  <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{label}</p>
                  <p className="text-xs text-gray-500 dark:text-slate-400">{desc}</p>
                </Link>
              ))}
              {doc.status !== 'ready' && (
                <p className="text-xs text-gray-400 dark:text-slate-500">Actions are available once the document is ready.</p>
              )}
            </div>
          </Card>

          {/* Activity Timeline */}
          {timeline.length > 0 && (
            <Card>
              <CardHeader title="Activity" />
              <ActivityTimeline events={timeline} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
