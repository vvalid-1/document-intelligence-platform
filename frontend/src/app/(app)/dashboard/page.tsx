'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listDocuments, getDocumentStats } from '@/lib/api/documents';
import type { DocumentResponse, DocumentStatsResponse } from '@/types/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { statusBadge } from '@/components/ui/Badge';
import { useAuthStore } from '@/lib/store/auth';

const STAT_CARDS = [
  {
    key: 'total' as const,
    label: 'Documents',
    color: 'blue' as const,
    href: '/documents',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    key: 'ready' as const,
    label: 'Ready',
    color: 'emerald' as const,
    href: '/documents',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    key: 'reviews' as const,
    label: 'Reviews',
    color: 'violet' as const,
    href: '/documents',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
    ),
  },
  {
    key: 'edits' as const,
    label: 'Edits',
    color: 'indigo' as const,
    href: '/documents',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
  },
  {
    key: 'signatures' as const,
    label: 'Signatures',
    color: 'pink' as const,
    href: '/documents',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
      </svg>
    ),
  },
  {
    key: 'favorites' as const,
    label: 'Starred',
    color: 'amber' as const,
    href: '/favorites',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
      </svg>
    ),
  },
  {
    key: 'folders' as const,
    label: 'Folders',
    color: 'sky' as const,
    href: '/folders',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7a2 2 0 012-2h3.586a1 1 0 01.707.293L11 7h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
      </svg>
    ),
  },
  {
    key: 'trash' as const,
    label: 'Trash',
    color: 'rose' as const,
    href: '/trash',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    ),
  },
  {
    key: 'media_analyses' as const,
    label: 'Media',
    color: 'violet' as const,
    href: '/documents',
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
      </svg>
    ),
  },
] as const;

type StatKey = typeof STAT_CARDS[number]['key'];

const colorMap: Record<string, string> = {
  blue:   'bg-blue-500/10 text-blue-400',
  emerald:'bg-emerald-500/10 text-emerald-400',
  violet: 'bg-violet-500/10 text-violet-400',
  indigo: 'bg-indigo-500/10 text-indigo-400',
  pink:   'bg-pink-500/10 text-pink-400',
  amber:  'bg-amber-500/10 text-amber-400',
  sky:    'bg-sky-500/10 text-sky-400',
  rose:   'bg-rose-500/10 text-rose-400',
};

function fmtDate(s: string) {
  return new Date(s).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function activityLabel(doc: DocumentResponse): string {
  if (doc.status === 'ready') return 'Processed and ready';
  if (doc.status === 'processing') return 'Processing…';
  if (doc.status === 'error') return 'Processing failed';
  return 'Uploaded';
}

function statusDot(status: string) {
  const cls: Record<string, string> = {
    ready: 'bg-emerald-400',
    processing: 'bg-amber-400 animate-pulse',
    error: 'bg-rose-400',
  };
  return cls[status] ?? 'bg-slate-600';
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DocumentStatsResponse | null>(null);
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    Promise.all([getDocumentStats(), listDocuments(1, 10)])
      .then(([s, r]) => {
        setStats(s);
        setDocs(r.items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const statValues: Record<StatKey, number> = {
    total: stats?.total ?? 0,
    ready: stats?.ready ?? 0,
    reviews: stats?.reviews ?? 0,
    edits: stats?.edits ?? 0,
    signatures: stats?.signatures ?? 0,
    favorites: stats?.favorites ?? 0,
    trash: stats?.trash ?? 0,
    folders: stats?.folders ?? 0,
    media_analyses: stats?.media_analyses ?? 0,
  };

  const firstName = user?.full_name?.split(' ')[0] ?? 'there';

  return (
    <div className="min-h-screen p-8">
      {/* Hero header */}
      <div className="mb-8 flex items-start justify-between gap-6">
        <div className="animate-fade-in">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-400">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
            AI Platform Active
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Good morning, {firstName}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <Link href="/documents/upload">
          <Button size="lg" variant="primary">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            Upload document
          </Button>
        </Link>
      </div>

      {/* Stats grid */}
      <div className="mb-8 grid grid-cols-3 gap-4 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-9">
        {STAT_CARDS.map(({ key, label, color, href, icon }, i) => (
          <Link key={key} href={href} className="group animate-fade-in" style={{ animationDelay: `${i * 40}ms` }}>
            <div className="flex flex-col rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4 backdrop-blur-xl transition-all duration-300 hover:border-white/[0.12] hover:bg-white/[0.06] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.4)]">
              <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl ${colorMap[color]}`}>
                {icon}
              </div>
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-600">{label}</p>
              {loading ? (
                <div className="mt-1 h-7 w-10 rounded shimmer" />
              ) : (
                <p className="mt-1 text-2xl font-bold tracking-tight text-slate-100">{statValues[key]}</p>
              )}
            </div>
          </Link>
        ))}
      </div>

      {/* Content grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent documents table */}
        <div className="lg:col-span-2 animate-fade-in" style={{ animationDelay: '120ms' }}>
          <Card padding={false}>
            <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h2 className="text-sm font-semibold text-slate-100">Recent documents</h2>
              </div>
              <Link href="/documents" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                View all →
              </Link>
            </div>

            {loading ? (
              <div className="space-y-1 p-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-12 rounded-xl shimmer" />
                ))}
              </div>
            ) : docs.length === 0 ? (
              <div className="py-16 text-center">
                <div className="mb-3 flex justify-center text-slate-700">
                  <svg width="40" height="40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <p className="text-sm text-slate-500">No documents yet.</p>
                <Link href="/documents/upload" className="mt-2 inline-block text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
                  Upload your first document →
                </Link>
              </div>
            ) : (
              <ul className="divide-y divide-white/[0.04]">
                {docs.slice(0, 7).map((doc) => (
                  <li key={doc.id}>
                    <Link
                      href={`/documents/${doc.id}`}
                      className="flex items-center justify-between px-6 py-3.5 transition-colors hover:bg-white/[0.03]"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] text-slate-500">
                          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-200">{doc.title}</p>
                          <p className="truncate text-xs text-slate-600">{doc.original_name}</p>
                        </div>
                      </div>
                      <div className="ml-4 flex shrink-0 items-center gap-3">
                        {statusBadge(doc.status)}
                        <span className="text-xs text-slate-600">
                          {doc.page_count != null ? `${doc.page_count}p` : '—'}
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* Activity feed */}
        <div className="animate-fade-in" style={{ animationDelay: '160ms' }}>
          <Card>
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/10 text-violet-400">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-slate-100">Activity</h2>
            </div>

            {loading ? (
              <div className="space-y-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="h-7 w-7 rounded-full shrink-0 shimmer" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 w-3/4 rounded shimmer" />
                      <div className="h-2.5 w-1/2 rounded shimmer" />
                    </div>
                  </div>
                ))}
              </div>
            ) : docs.length === 0 ? (
              <p className="text-sm text-slate-600">No activity yet.</p>
            ) : (
              <ul className="space-y-4">
                {docs.slice(0, 5).map((doc) => (
                  <li key={doc.id} className="flex gap-3">
                    <div className="relative mt-1 flex-shrink-0">
                      <span className={`block h-2.5 w-2.5 rounded-full ${statusDot(doc.status)}`} />
                    </div>
                    <Link href={`/documents/${doc.id}`} className="group min-w-0">
                      <p className="truncate text-xs font-medium text-slate-300 group-hover:text-white transition-colors">{doc.title}</p>
                      <p className="text-xs text-slate-600">{activityLabel(doc)}</p>
                      <p className="mt-0.5 text-[11px] text-slate-700">{fmtDate(doc.updated_at)}</p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Quick actions */}
          <Card className="mt-4">
            <div className="mb-4 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-slate-100">Quick actions</h2>
            </div>
            <div className="space-y-2">
              {[
                { href: '/documents/upload', label: 'Upload new document', icon: '↑' },
                { href: '/search', label: 'Search documents', icon: '⌕' },
                { href: '/folders', label: 'Browse folders', icon: '⊞' },
              ].map((a) => (
                <Link
                  key={a.href}
                  href={a.href}
                  className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-400 transition-all hover:bg-white/[0.05] hover:text-slate-200"
                >
                  <span className="text-xs text-slate-600">{a.icon}</span>
                  {a.label}
                  <svg className="ml-auto" width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
