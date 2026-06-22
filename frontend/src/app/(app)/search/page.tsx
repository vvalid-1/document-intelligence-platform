'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { searchDocuments } from '@/lib/api/search';
import { listFolders } from '@/lib/api/folders';
import type { FolderResponse, SearchGroup, SearchResponse } from '@/types/api';
import { Card } from '@/components/ui/Card';

const EXAMPLES = [
  'Find all budget references',
  'Documents mentioning scholarships',
  'References to 2026',
  'Digital literacy topics',
];

function SimilarityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-indigo-500' : pct >= 40 ? 'bg-amber-500' : 'bg-slate-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] tabular-nums text-slate-600">{pct}%</span>
    </div>
  );
}

function GroupCard({ group, documentId }: { group: SearchGroup; documentId: string }) {
  const [expanded, setExpanded] = useState(false);
  const visibleHits = expanded ? group.hits : group.hits.slice(0, 2);

  return (
    <Card hover>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Link href={`/documents/${documentId}`} className="text-sm font-semibold text-indigo-400 hover:text-indigo-300 transition-colors">
              {group.document_title}
            </Link>
            <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400">
              {group.match_count} match{group.match_count !== 1 ? 'es' : ''}
            </span>
          </div>
          <div className="mt-1">
            <SimilarityBar score={group.best_similarity} />
          </div>
        </div>
        <Link
          href={`/documents/${documentId}`}
          className="shrink-0 rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-300 transition-all hover:border-indigo-500/30 hover:text-indigo-300"
        >
          Open
        </Link>
      </div>

      <div className="mt-3 space-y-2">
        {visibleHits.map((hit, i) => (
          <div key={i} className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3">
            {hit.page_number != null && (
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Page {hit.page_number}</p>
            )}
            <p className="text-sm leading-relaxed text-slate-300 line-clamp-3">{hit.excerpt}</p>
          </div>
        ))}
      </div>

      {group.hits.length > 2 && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
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
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void listFolders().then((r) => setFolders(r.items)).catch(() => {});
    inputRef.current?.focus();
  }, []);

  async function handleSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true); setError(''); setResults(null);
    try {
      const res = await searchDocuments(trimmed, 20, selectedFolder || null);
      setResults(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) { e.preventDefault(); void handleSearch(query); }

  const hasResults = results !== null;

  return (
    <div className="flex h-full flex-col">
      {/* Search header */}
      <div className="border-b border-white/[0.06] bg-white/[0.02] px-8 py-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h1 className="text-lg font-semibold text-slate-100">Search</h1>
        </div>

        <form onSubmit={onSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-600">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search across all documents…"
              className="w-full rounded-2xl border border-white/[0.08] bg-white/[0.04] py-3 pl-11 pr-4 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/40 transition-all duration-200"
            />
          </div>
          {folders.length > 0 && (
            <select
              value={selectedFolder}
              onChange={(e) => setSelectedFolder(e.target.value)}
              className="rounded-2xl border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-sm text-slate-300 focus:border-indigo-500/50 focus:outline-none"
            >
              <option value="">All folders</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          )}
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="rounded-2xl bg-gradient-to-r from-indigo-500 to-violet-600 px-6 py-3 text-sm font-semibold text-white shadow-[0_4px_16px_rgba(99,102,241,0.4)] transition-all hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Searching…
              </span>
            ) : 'Search'}
          </button>
        </form>

        {hasResults && !loading && (
          <p className="mt-3 text-xs text-slate-500">
            {results!.total_hits === 0
              ? `No results for "${results!.query}"`
              : `${results!.total_hits} match${results!.total_hits !== 1 ? 'es' : ''} across ${results!.total_documents} document${results!.total_documents !== 1 ? 's' : ''}`}
          </p>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-8 py-6 scrollbar-thin">
        {error && (
          <div className="mb-6 flex items-center gap-2.5 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
            <svg width="16" height="16" className="shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            {error}
          </div>
        )}

        {!hasResults && !loading && !error && (
          <div className="flex flex-col items-center py-16 text-center animate-fade-in">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10">
              <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25} className="text-indigo-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h2 className="mb-2 text-base font-semibold text-slate-200">Search your library</h2>
            <p className="mb-6 max-w-sm text-sm text-slate-500">
              Enter any natural language query to find relevant passages across all your documents.
            </p>
            <div className="grid grid-cols-2 gap-2 text-left">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => { setQuery(ex); inputRef.current?.focus(); }}
                  className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-2.5 text-sm text-slate-400 transition-all hover:border-indigo-500/30 hover:bg-white/[0.06] hover:text-slate-200"
                >
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="shrink-0 text-slate-600">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <div className="mb-4 flex items-center gap-3">
                  <div className="h-4 w-40 rounded-lg shimmer" />
                  <div className="h-4 w-16 rounded-full shimmer" />
                </div>
                <div className="space-y-2">
                  <div className="h-3 w-full rounded shimmer" />
                  <div className="h-3 w-5/6 rounded shimmer" />
                </div>
              </div>
            ))}
          </div>
        )}

        {hasResults && !loading && results!.total_hits === 0 && (
          <div className="flex flex-col items-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.04]">
              <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} className="text-slate-500">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h2 className="mb-1 text-base font-semibold text-slate-200">No results found</h2>
            <p className="text-sm text-slate-500">Try different keywords or upload more documents.</p>
          </div>
        )}

        {hasResults && !loading && results!.total_hits > 0 && (
          <div className="space-y-4 animate-fade-in">
            {results!.groups.map((group) => (
              <GroupCard key={group.document_id} group={group} documentId={group.document_id} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
