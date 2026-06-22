'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { getMediaAnalysis, retriggerMediaAnalysis } from '@/lib/api/media';
import { getDocument } from '@/lib/api/documents';
import type { DocumentResponse, MediaAnalysisResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { getToken } from '@/lib/api/client';

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m} min ${s} s` : `${s} s`;
}

function SectionCard({
  title,
  items,
  icon,
  emptyText,
}: {
  title: string;
  items: string[];
  icon: string;
  emptyText: string;
}) {
  return (
    <Card>
      <CardHeader title={`${icon} ${title}`} />
      {items.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-slate-500">{emptyText}</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-slate-300">
              <span className="mt-0.5 shrink-0 text-gray-400 dark:text-slate-500">•</span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function DownloadButton({ href, label }: { href: string; label: string }) {
  const token = getToken();
  return (
    <a
      href={href}
      download
      onClick={(e) => {
        e.preventDefault();
        fetch(href, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
          .then((r) => r.blob())
          .then((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = label;
            a.click();
            URL.revokeObjectURL(url);
          });
      }}
      className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-slate-600 dark:text-slate-300 dark:hover:border-blue-500 dark:hover:bg-blue-900/20 dark:hover:text-blue-300"
    >
      ↓ {label}
    </a>
  );
}

export default function MediaAnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [analysis, setAnalysis] = useState<MediaAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retrigering, setRetriggering] = useState(false);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [d, a] = await Promise.all([
        getDocument(id),
        getMediaAnalysis(id).catch(() => null),
      ]);
      setDoc(d);
      setAnalysis(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleRetrigger() {
    setRetriggering(true);
    setError('');
    try {
      const a = await retriggerMediaAnalysis(id);
      setAnalysis(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to re-run analysis');
    } finally {
      setRetriggering(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  const isMedia =
    doc?.mime_type === 'audio/mpeg' ||
    doc?.mime_type === 'audio/wav' ||
    doc?.mime_type === 'video/mp4';

  const versionId = analysis?.version_id;
  const txtDownloadUrl = versionId
    ? `/api/v1/documents/${id}/versions/${versionId}/download?fmt=txt`
    : null;
  const pdfDownloadUrl = versionId
    ? `/api/v1/documents/${id}/versions/${versionId}/download?fmt=pdf`
    : null;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href={`/documents/${id}`} className="text-sm text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200">
              ← {doc?.title ?? 'Document'}
            </Link>
          </div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">🎙 Media Analysis</h1>
          {doc && (
            <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">
              {doc.original_name}
              {doc.media_duration_seconds != null && ` · ${formatDuration(doc.media_duration_seconds)}`}
              {analysis?.language && ` · ${analysis.language.toUpperCase()}`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {analysis && (
            <>
              {txtDownloadUrl && (
                <DownloadButton href={txtDownloadUrl} label="Transcript.txt" />
              )}
              {pdfDownloadUrl && (
                <DownloadButton href={pdfDownloadUrl} label="Summary.pdf" />
              )}
            </>
          )}
          <Button
            variant="secondary"
            size="sm"
            loading={retrigering}
            onClick={() => void handleRetrigger()}
          >
            Re-analyze
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </div>
      )}

      {!isMedia && doc && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
          This document is not an audio or video file (MP3/WAV/MP4).
        </div>
      )}

      {doc?.status === 'processing' && !analysis && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-300">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          {doc.processing_step === 'transcribing'
            ? 'Transcribing audio — this may take a few minutes…'
            : doc.processing_step === 'analyzing'
            ? 'Running AI analysis…'
            : 'Processing — please wait…'}
        </div>
      )}

      {!analysis ? (
        <div className="py-16 text-center">
          <p className="text-3xl mb-3">🎙</p>
          <p className="font-medium text-gray-700 dark:text-slate-300">No analysis available yet</p>
          <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
            {doc?.status === 'ready'
              ? 'Analysis may have failed during processing.'
              : 'Analysis will appear here once the document finishes processing.'}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary */}
          <Card>
            <CardHeader title="Executive Summary" />
            {analysis.summary ? (
              <p className="text-sm leading-relaxed text-gray-700 dark:text-slate-300">
                {analysis.summary}
              </p>
            ) : (
              <p className="text-sm text-gray-400 dark:text-slate-500">No summary generated.</p>
            )}
          </Card>

          {/* Topics + Action Items side by side */}
          <div className="grid gap-4 lg:grid-cols-2">
            <SectionCard
              title="Key Topics"
              icon="🏷"
              items={analysis.key_topics}
              emptyText="No key topics identified."
            />
            <SectionCard
              title="Action Items"
              icon="✅"
              items={analysis.action_items}
              emptyText="No action items identified."
            />
          </div>

          {/* Dates + Numbers side by side */}
          <div className="grid gap-4 lg:grid-cols-2">
            <SectionCard
              title="Important Dates"
              icon="📅"
              items={analysis.important_dates}
              emptyText="No important dates identified."
            />
            <SectionCard
              title="Important Numbers"
              icon="🔢"
              items={analysis.important_numbers}
              emptyText="No important numbers identified."
            />
          </div>

          {/* Transcript */}
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100">📝 Full Transcript</h3>
              {txtDownloadUrl && (
                <DownloadButton href={txtDownloadUrl} label="Transcript.txt" />
              )}
            </div>
            <div className="max-h-96 overflow-y-auto rounded-lg bg-gray-50 p-4 dark:bg-slate-700/50">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700 dark:text-slate-300">
                {analysis.transcript || 'No transcript available.'}
              </p>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
