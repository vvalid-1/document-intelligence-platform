'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { reviewDocument } from '@/lib/api/reviews';
import type { ReviewIssue, ReviewResponse } from '@/types/api';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';
import { severityBadge } from '@/components/ui/Badge';

function ScoreRing({ value }: { value: number | null }) {
  if (value == null) return null;
  const pct = Math.round(value * 10);
  const color = pct >= 8 ? 'text-emerald-400' : pct >= 6 ? 'text-indigo-400' : pct >= 4 ? 'text-amber-400' : 'text-rose-400';
  const bgRing = pct >= 8 ? 'stroke-emerald-500/30' : pct >= 6 ? 'stroke-indigo-500/30' : pct >= 4 ? 'stroke-amber-500/30' : 'stroke-rose-500/30';
  const fgRing = pct >= 8 ? 'stroke-emerald-400' : pct >= 6 ? 'stroke-indigo-400' : pct >= 4 ? 'stroke-amber-400' : 'stroke-rose-400';
  const dasharray = 2 * Math.PI * 40;
  const dashoffset = dasharray * (1 - pct / 10);
  return (
    <div className="flex items-center gap-4">
      <div className="relative h-24 w-24 shrink-0">
        <svg className="h-24 w-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" strokeWidth="8" className={bgRing} />
          <circle cx="50" cy="50" r="40" fill="none" strokeWidth="8" strokeLinecap="round" className={fgRing} strokeDasharray={dasharray} strokeDashoffset={dashoffset} style={{ transition: 'stroke-dashoffset 1s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-bold ${color}`}>{pct}</span>
          <span className="text-[10px] text-slate-600">/10</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-100">Overall score</p>
        <p className="text-xs text-slate-500">
          {pct >= 8 ? 'Excellent quality' : pct >= 6 ? 'Good — minor issues' : pct >= 4 ? 'Needs improvement' : 'Significant issues'}
        </p>
      </div>
    </div>
  );
}

function IssueRow({ issue }: { issue: ReviewIssue }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
      <div className="mb-2 flex items-center gap-2">
        {severityBadge(issue.severity)}
        <span className="text-xs font-medium text-slate-400 capitalize">{issue.type}</span>
      </div>
      <p className="text-sm text-slate-200 leading-relaxed">{issue.description}</p>
      {issue.location && (
        <p className="mt-1.5 text-xs text-slate-600">Location: {issue.location}</p>
      )}
      {issue.suggestion && (
        <p className="mt-1.5 rounded-lg bg-indigo-500/[0.06] px-3 py-2 text-xs text-indigo-300 italic">
          Suggestion: {issue.suggestion}
        </p>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleReview() {
    setLoading(true); setError('');
    try { const r = await reviewDocument(id); setReview(r); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Review failed'); }
    finally { setLoading(false); }
  }

  const severityCounts = review
    ? {
        high: review.issues.filter((i) => i.severity === 'high').length,
        medium: review.issues.filter((i) => i.severity === 'medium').length,
        low: review.issues.filter((i) => i.severity === 'low').length,
      }
    : null;

  return (
    <div className="flex h-full bg-[#0a0f1e]">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-white/[0.06] lg:flex lg:flex-col">
        <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-4 py-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="xs">
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </Button>
          </Link>
          <span className="text-xs text-slate-600">Document preview</span>
          <div className="w-16" />
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Review panel */}
      <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`} className="lg:hidden">
            <Button variant="ghost" size="xs">← Back</Button>
          </Link>
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">Document review</h1>
        </div>

        {!review ? (
          <div className="mx-auto max-w-md">
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-8 text-center shadow-[0_8px_40px_rgba(0,0,0,0.4)]">
              <div className="mb-4 flex justify-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-400">
                  <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </div>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed">
                The AI reviewer will analyze clarity, consistency, completeness, and identify issues in your document.
              </p>
              <p className="mt-1 text-xs text-slate-600">This may take 30–120 seconds on CPU.</p>
              {error && (
                <div className="mt-4 flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  {error}
                </div>
              )}
              {loading && (
                <p className="mt-3 text-xs text-slate-500 animate-pulse">Analyzing your document…</p>
              )}
              <Button className="mt-6 w-full" size="lg" loading={loading} onClick={() => void handleReview()}>
                Run AI review
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-5 animate-fade-in">
            {/* Score + summary */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6">
              <div className="mb-5 flex items-center justify-between gap-4">
                <ScoreRing value={review.overall_score != null ? review.overall_score / 10 : null} />
                {severityCounts && (
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="h-2 w-2 rounded-full bg-rose-400" />
                      <span className="text-slate-400">{severityCounts.high} high</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="h-2 w-2 rounded-full bg-amber-400" />
                      <span className="text-slate-400">{severityCounts.medium} medium</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="h-2 w-2 rounded-full bg-blue-400" />
                      <span className="text-slate-400">{severityCounts.low} low</span>
                    </div>
                  </div>
                )}
              </div>
              {review.summary && (
                <p className="text-sm text-slate-300 leading-relaxed border-t border-white/[0.06] pt-4">{review.summary}</p>
              )}
            </div>

            {/* Issues */}
            {review.issues.length > 0 && (
              <div>
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="text-amber-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  Issues <span className="text-slate-600">({review.issues.length})</span>
                </div>
                <div className="space-y-2">
                  {review.issues.slice().sort((a, b) => {
                    const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
                    return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
                  }).map((issue, i) => (
                    <IssueRow key={i} issue={issue} />
                  ))}
                </div>
              </div>
            )}

            <Button variant="secondary" onClick={() => void handleReview()} loading={loading}>
              Run again
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
