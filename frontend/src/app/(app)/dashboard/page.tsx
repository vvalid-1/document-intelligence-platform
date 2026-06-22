'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listDocuments, getDocumentStats } from '@/lib/api/documents';
import type { DocumentResponse, DocumentStatsResponse } from '@/types/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { statusBadge } from '@/components/ui/Badge';

const STAT_CARDS = [
  { key: 'total' as const, label: 'Total documents', icon: '⎙', iconCls: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400', href: '/documents' },
  { key: 'ready' as const, label: 'Ready', icon: '✓', iconCls: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400', href: '/documents' },
  { key: 'reviews' as const, label: 'Reviews done', icon: '🔍', iconCls: 'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400', href: '/documents' },
  { key: 'edits' as const, label: 'Edits created', icon: '✏', iconCls: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400', href: '/documents' },
  { key: 'signatures' as const, label: 'Signatures', icon: '✍', iconCls: 'bg-pink-50 text-pink-600 dark:bg-pink-900/30 dark:text-pink-400', href: '/documents' },
  { key: 'favorites' as const, label: 'Starred', icon: '★', iconCls: 'bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400', href: '/favorites' },
  { key: 'trash' as const, label: 'In trash', icon: '🗑', iconCls: 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400', href: '/trash' },
  { key: 'folders' as const, label: 'Folders', icon: '📁', iconCls: 'bg-sky-50 text-sky-600 dark:bg-sky-900/30 dark:text-sky-400', href: '/folders' },
] as const;

type StatKey = typeof STAT_CARDS[number]['key'];

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

export default function DashboardPage() {
  const [stats, setStats] = useState<DocumentStatsResponse | null>(null);
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);

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
  };

  return (
    <div className="p-8">
      <div className="mb-7 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Dashboard</h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">Welcome back</p>
        </div>
        <Link href="/documents/upload">
          <Button>Upload document</Button>
        </Link>
      </div>

      <div className="mb-7 grid grid-cols-2 gap-4 xl:grid-cols-8">
        {STAT_CARDS.map(({ key, label, icon, iconCls, href }) => (
          <Link key={key} href={href} className="group">
            <Card>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-slate-400 group-hover:text-gray-700 dark:group-hover:text-slate-300">{label}</p>
                  <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900 dark:text-slate-100">
                    {loading ? '—' : statValues[key]}
                  </p>
                </div>
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-base font-semibold ${iconCls}`}>
                  {icon}
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card padding={false}>
            <div className="border-b border-gray-100 px-6 py-4 dark:border-slate-700">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Recent documents</h2>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              </div>
            ) : docs.length === 0 ? (
              <div className="py-12 text-center">
                <p className="text-sm text-gray-500 dark:text-slate-400">No documents yet.</p>
                <Link href="/documents/upload" className="mt-2 inline-block text-sm text-blue-600 hover:underline dark:text-blue-400">
                  Upload your first document
                </Link>
              </div>
            ) : (
              <ul className="divide-y divide-gray-100 dark:divide-slate-700">
                {docs.slice(0, 7).map((doc) => (
                  <li key={doc.id}>
                    <Link
                      href={`/documents/${doc.id}`}
                      className="flex items-center justify-between px-6 py-3.5 transition-colors hover:bg-gray-50 dark:hover:bg-slate-700/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-gray-900 dark:text-slate-100">{doc.title}</p>
                        <p className="text-xs text-gray-400 dark:text-slate-500">{doc.original_name}</p>
                      </div>
                      <div className="ml-4 flex shrink-0 items-center gap-3">
                        {statusBadge(doc.status)}
                        <span className="text-xs text-gray-400 dark:text-slate-500">
                          {doc.page_count != null ? `${doc.page_count}p` : '—'}
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {docs.length > 0 && (
              <div className="border-t border-gray-100 px-6 py-3 dark:border-slate-700">
                <Link href="/documents" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
                  View all documents →
                </Link>
              </div>
            )}
          </Card>
        </div>

        <div>
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-gray-900 dark:text-slate-100">Recent activity</h2>
            {loading ? (
              <div className="flex justify-center py-8">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              </div>
            ) : docs.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-slate-500">No activity yet.</p>
            ) : (
              <ul className="space-y-3">
                {docs.slice(0, 5).map((doc) => (
                  <li key={doc.id} className="flex items-start gap-3">
                    <div
                      className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                        doc.status === 'ready'
                          ? 'bg-emerald-500'
                          : doc.status === 'processing'
                          ? 'bg-amber-400'
                          : doc.status === 'error'
                          ? 'bg-red-500'
                          : 'bg-gray-400 dark:bg-slate-500'
                      }`}
                    />
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-gray-700 dark:text-slate-300">{doc.title}</p>
                      <p className="text-xs text-gray-400 dark:text-slate-500">{activityLabel(doc)}</p>
                      <p className="mt-0.5 text-xs text-gray-400 dark:text-slate-600">{fmtDate(doc.updated_at)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
