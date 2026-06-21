'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { reviewDocument } from '@/lib/api/reviews';
import type { ReviewIssue, ReviewResponse } from '@/types/api';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { severityBadge } from '@/components/ui/Badge';

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = value != null ? Math.round(value * 100) : null;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{pct != null ? `${pct}%` : '—'}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-gray-100">
        <div
          className="h-1.5 rounded-full bg-blue-500 transition-all"
          style={{ width: `${pct ?? 0}%` }}
        />
      </div>
    </div>
  );
}

function IssueRow({ issue }: { issue: ReviewIssue }) {
  return (
    <div className="rounded-lg border border-gray-100 p-4">
      <div className="mb-1 flex items-center gap-2">
        {severityBadge(issue.severity)}
        <span className="text-xs font-medium text-gray-700 capitalize">{issue.type}</span>
      </div>
      <p className="text-sm text-gray-800">{issue.description}</p>
      {issue.location && (
        <p className="mt-1 text-xs text-gray-500">Location: {issue.location}</p>
      )}
      {issue.suggestion && (
        <p className="mt-1 text-xs text-gray-500 italic">Suggestion: {issue.suggestion}</p>
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
    setLoading(true);
    setError('');
    try {
      const r = await reviewDocument(id);
      setReview(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-gray-200 lg:flex lg:flex-col">
        <div className="border-b border-gray-200 bg-white px-4 py-2">
          <span className="text-xs font-medium text-gray-500">Document preview</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Review panel */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="sm">←</Button>
          </Link>
          <h1 className="text-xl font-bold text-gray-900">Document review</h1>
        </div>

        {!review ? (
          <div className="mx-auto max-w-lg">
            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-600">
                  The AI reviewer will analyze clarity, consistency, completeness, and identify issues.
                </p>
                <p className="mt-1 text-xs text-gray-400">This may take 30–120 seconds.</p>
                {error && (
                  <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
                )}
                <Button className="mt-5 w-full" loading={loading} onClick={() => void handleReview()}>
                  Run AI review
                </Button>
              </div>
            </Card>
          </div>
        ) : (
          <div className="space-y-6">
            <Card>
              <CardHeader
                title="Review summary"
                subtitle={`${review.issue_count} issue${review.issue_count !== 1 ? 's' : ''} found`}
              />
              <p className="text-sm text-gray-700 leading-relaxed">{review.summary ?? '—'}</p>

              <div className="mt-5 space-y-3">
                <ScoreBar
                  label="Overall score"
                  value={review.overall_score != null ? review.overall_score / 10 : null}
                />
              </div>
            </Card>

            {review.issues.length > 0 && (
              <Card>
                <CardHeader title="Issues" subtitle="Ordered by severity" />
                <div className="space-y-3">
                  {review.issues
                    .slice()
                    .sort((a, b) => {
                      const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
                      return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
                    })
                    .map((issue, i) => (
                      <IssueRow key={i} issue={issue} />
                    ))}
                </div>
              </Card>
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
