'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { searchDocuments } from '@/lib/api/search';
import type { SearchGroup, SearchResponse } from '@/types/api';
import { Card } from '@/components/ui/Card';

const EXAMPLES = [
  'Find all budget references',
  'Documents mentioning scholarships',
  'References to 2026',
  'Digital literacy topics',
];

function SimilarityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-blue-500' : pct >= 40 ? 'bg-amber-500' : 'bg-gray-400';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200 dark:bg-slate-700">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] tabular-nums text-gray-400 dark:text-slate-500">{pct}%</span>
    </div>
  );
}

function GroupCard({ group, documentId }: { group: SearchGroup; documentId: string }) {
  const [expanded, setExpanded] = useState(false);
  const visibleHits = expanded ? group.hits : group.hits.slice(0, 2);

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              href={`/documents/${documentId}`}
              className="text-sm font-semibold text-blue-600 hover:underline dark:text-blue-400"
            >
              {group.document_title}
            </Link>
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
              {group.match_count} match{group.match_count !== 1 ? 'es' : ''}
            </span>
          </div>
          <SimilarityBar score={group.best_similarity} />
        </div>
        <Link
          href={`/documents/${documentId}`}
          className="shrink-0 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-slate-600 dark:text-slate-300 dark:hover:border-blue-500 dark:hover:bg-blue-900/20 dark:hover:text-blue-300"
        >
          Open
        </Link>
      </div>

      <div className="mt-3 space-y-2">
        {visibleHits.map((hit, i) => (
          <div
            key={i}
            className="rounded-lg bg-gray-50 px-3 py-2.5 dark:bg-slate-800"
          >
            {hit.page_number != null && (
              <p className="mb-1 text-[11px] font-medium text-gray-400 dark:text-slate-500">
                Page {hit.page_number}
              </p>
            )}
            <p className="text-sm leading-relaxed text-gray-700 dark:text-slate-300 line-clamp-3">
              {hit.excerpt}
            </p>
          </div>
        ))}
      </div>

      {group.hits.length > 2 && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 text-xs text-blue-600 hover:underline dark:text-blue-400"
        >
          {expanded ? 'Show less' : `Show ${group.hits.length - 2} more match${group.hits.length - 2 !== 1 ? 'es' : ''}`}
        </button>
      )}
    </Card>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError('');
    setResults(null);
    try {
      const res = await searchDocuments(trimmed, 20);
      setResults(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void handleSearch(query);
  }

  const hasQuery = query.trim().length > 0;
  const hasResults = results !== null;

  return (
    <div className="flex h-full flex-col">
      {/* Search header */}
      <div className="border-b border-gray-200 bg-white px-8 py-6 dark:border-slate-700 dark:bg-slate-900">
        <h1 className="mb-4 text-xl font-bold text-gray-900 dark:text-slate-100">Search</h1>
        <form onSubmit={onSubmit} className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search across all documents…"
            className="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 placeholder-gray-400 shadow-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:border-blue-400"
          />
          <button
            type="submit"
            disabled={!hasQuery || loading}
            className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Searching…
              </span>
            ) : (
              'Search'
            )}
          </button>
        </form>

        {/* Result summary */}
        {hasResults && !loading && (
          <p className="mt-3 text-sm text-gray-500 dark:text-slate-400">
            {results!.total_hits === 0
              ? `No results for "${results!.query}"`
              : `${results!.total_hits} match${results!.total_hits !== 1 ? 'es' : ''} across ${results!.total_documents} document${results!.total_documents !== 1 ? 's' : ''} for "${results!.query}"`}
          </p>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-8 py-6">
        {/* Error */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Empty state — no query yet */}
        {!hasResults && !loading && !error && (
          <div className="flex flex-col items-center py-16 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 dark:bg-blue-900/20">
              <span className="text-3xl">🔍</span>
            </div>
            <h2 className="mb-2 text-base font-semibold text-gray-800 dark:text-slate-200">
              Search your document library
            </h2>
            <p className="mb-6 max-w-sm text-sm text-gray-500 dark:text-slate-400">
              Enter any natural language query to find relevant passages across all your uploaded documents.
            </p>
            <div className="space-y-2 text-left">
              <p className="text-xs font-medium text-gray-400 dark:text-slate-500 text-center mb-3">Examples</p>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => {
                    setQuery(ex);
                    inputRef.current?.focus();
                  }}
                  className="block w-full rounded-lg border border-gray-200 px-4 py-2.5 text-left text-sm text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-slate-700 dark:text-slate-300 dark:hover:border-blue-500 dark:hover:bg-blue-900/20 dark:hover:text-blue-300"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse rounded-xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                <div className="mb-3 h-4 w-48 rounded bg-gray-200 dark:bg-slate-700" />
                <div className="space-y-2">
                  <div className="h-3 w-full rounded bg-gray-100 dark:bg-slate-700" />
                  <div className="h-3 w-5/6 rounded bg-gray-100 dark:bg-slate-700" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* No results */}
        {hasResults && !loading && results!.total_hits === 0 && (
          <div className="flex flex-col items-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100 dark:bg-slate-800">
              <span className="text-2xl">📭</span>
            </div>
            <h2 className="mb-1 text-base font-semibold text-gray-800 dark:text-slate-200">No results found</h2>
            <p className="text-sm text-gray-500 dark:text-slate-400">
              Try different keywords or upload more documents.
            </p>
          </div>
        )}

        {/* Results */}
        {hasResults && !loading && results!.total_hits > 0 && (
          <div className="space-y-4">
            {results!.groups.map((group) => (
              <GroupCard
                key={group.document_id}
                group={group}
                documentId={group.document_id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
