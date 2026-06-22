'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { getMediaAnalysis, retriggerMediaAnalysis } from '@/lib/api/media';
import { getDocument } from '@/lib/api/documents';
import type { DocumentResponse, MediaAnalysisResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
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
  accentClass,
}: {
  title: string;
  items: string[];
  icon: React.ReactNode;
  emptyText: string;
  accentClass: string;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
      <div className={`mb-4 flex items-center gap-2.5 text-sm font-semibold ${accentClass}`}>
        {icon}
        {title}
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-600">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm text-slate-300">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-600" />
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
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
            a.href = url; a.download = label; a.click();
            URL.revokeObjectURL(url);
          });
      }}
      className="inline-flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-slate-400 transition-all hover:border-indigo-500/30 hover:bg-indigo-500/[0.06] hover:text-indigo-300"
    >
      <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      {label}
    </a>
  );
}

export default function MediaAnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [analysis, setAnalysis] = useState<MediaAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retriggering, setRetriggering] = useState(false);

  async function load() {
    setLoading(true); setError('');
    try {
      const [d, a] = await Promise.all([getDocument(id), getMediaAnalysis(id).catch(() => null)]);
      setDoc(d); setAnalysis(a);
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to load'); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRetrigger() {
    setRetriggering(true); setError('');
    try { setAnalysis(await retriggerMediaAnalysis(id)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to re-run analysis'); }
    finally { setRetriggering(false); }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  const isMedia = doc?.mime_type === 'audio/mpeg' || doc?.mime_type === 'audio/wav' || doc?.mime_type === 'video/mp4';
  const versionId = analysis?.version_id;
  const txtDownloadUrl = versionId ? `/api/v1/documents/${id}/versions/${versionId}/download?fmt=txt` : null;
  const pdfDownloadUrl = versionId ? `/api/v1/documents/${id}/versions/${versionId}/download?fmt=pdf` : null;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <Link href={`/documents/${id}`} className="mb-2 flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-400 transition-colors">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            {doc?.title ?? 'Document'}
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-400">
              <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-100">Media Analysis</h1>
              {doc && (
                <p className="text-sm text-slate-500">
                  {doc.original_name}
                  {doc.media_duration_seconds != null && ` · ${formatDuration(doc.media_duration_seconds)}`}
                  {analysis?.language && ` · ${analysis.language.toUpperCase()}`}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {analysis && (
            <>
              {txtDownloadUrl && <DownloadButton href={txtDownloadUrl} label="Transcript.txt" />}
              {pdfDownloadUrl && <DownloadButton href={pdfDownloadUrl} label="Summary.pdf" />}
            </>
          )}
          <Button variant="glass" size="sm" loading={retriggering} onClick={() => void handleRetrigger()}>
            Re-analyze
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="shrink-0">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          {error}
        </div>
      )}

      {!isMedia && doc && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3 text-sm text-amber-400">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="shrink-0">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          This document is not an audio or video file (MP3/WAV/MP4).
        </div>
      )}

      {doc?.status === 'processing' && !analysis && (
        <div className="mb-4 flex items-center gap-2.5 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.06] px-4 py-3 text-sm text-indigo-400">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent shrink-0" />
          {doc.processing_step === 'transcribing'
            ? 'Transcribing audio — this may take a few minutes…'
            : doc.processing_step === 'analyzing'
            ? 'Running AI analysis…'
            : 'Processing — please wait…'}
        </div>
      )}

      {!analysis ? (
        <div className="py-20 text-center">
          <div className="mb-4 flex justify-center text-slate-700">
            <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          </div>
          <p className="text-slate-400 font-medium">No analysis available yet</p>
          <p className="mt-1 text-sm text-slate-600">
            {doc?.status === 'ready'
              ? 'Analysis may have failed during processing.'
              : 'Analysis will appear here once the document finishes processing.'}
          </p>
        </div>
      ) : (
        <div className="space-y-5 animate-fade-in">
          {/* Summary */}
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6">
            <div className="mb-3 flex items-center gap-2.5 text-sm font-semibold text-slate-100">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-violet-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Executive Summary
            </div>
            {analysis.summary ? (
              <p className="text-sm leading-relaxed text-slate-300">{analysis.summary}</p>
            ) : (
              <p className="text-sm text-slate-600">No summary generated.</p>
            )}
          </div>

          {/* Topics + Action Items */}
          <div className="grid gap-4 lg:grid-cols-2">
            <SectionCard
              title="Key Topics"
              icon={<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg>}
              items={analysis.key_topics}
              emptyText="No key topics identified."
              accentClass="text-sky-400"
            />
            <SectionCard
              title="Action Items"
              icon={<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg>}
              items={analysis.action_items}
              emptyText="No action items identified."
              accentClass="text-emerald-400"
            />
          </div>

          {/* Dates + Numbers */}
          <div className="grid gap-4 lg:grid-cols-2">
            <SectionCard
              title="Important Dates"
              icon={<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>}
              items={analysis.important_dates}
              emptyText="No important dates identified."
              accentClass="text-amber-400"
            />
            <SectionCard
              title="Important Numbers"
              icon={<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" /></svg>}
              items={analysis.important_numbers}
              emptyText="No important numbers identified."
              accentClass="text-indigo-400"
            />
          </div>

          {/* Transcript */}
          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5 text-sm font-semibold text-slate-100">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-violet-400">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h7" />
                </svg>
                Full Transcript
              </div>
              {txtDownloadUrl && <DownloadButton href={txtDownloadUrl} label="Transcript.txt" />}
            </div>
            <div className="max-h-96 overflow-y-auto rounded-xl border border-white/[0.05] bg-black/20 p-4 scrollbar-thin">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-400">
                {analysis.transcript || 'No transcript available.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
