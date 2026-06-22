'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listDocuments, unfavoriteDocument } from '@/lib/api/documents';
import type { DocumentResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { statusBadge } from '@/components/ui/Badge';

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function FavoritesPage() {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [unstarringId, setUnstarringId] = useState<string | null>(null);

  async function load(p: number, silent = false) {
    if (!silent) setLoading(true);
    try { const r = await listDocuments(p, 20, { favorite: true }); setDocs(r.items); setTotal(r.total); }
    catch { /* ignore */ } finally { if (!silent) setLoading(false); }
  }

  useEffect(() => { void load(page); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleUnstar(id: string) {
    setUnstarringId(id);
    try { await unfavoriteDocument(id); await load(page, true); } catch { /* ignore */ } finally { setUnstarringId(null); }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Starred</h1>
          <p className="mt-0.5 text-sm text-slate-500">{total} starred document{total !== 1 ? 's' : ''}</p>
        </div>
      </div>

      <Card padding={false}>
        {loading ? (
          <div className="space-y-2 p-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-14 rounded-xl shimmer" />)}
          </div>
        ) : docs.length === 0 ? (
          <div className="py-20 text-center">
            <div className="mb-4 flex justify-center text-slate-700">
              <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
            </div>
            <p className="text-slate-500">No starred documents yet.</p>
            <p className="mt-1 text-sm text-slate-600">
              Star documents from the{' '}
              <Link href="/documents" className="text-indigo-400 hover:text-indigo-300 transition-colors">Documents page</Link>{' '}
              to find them quickly.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.05]">
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Document</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Status</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Size</th>
                <th className="px-6 py-3 text-right text-[11px] font-semibold uppercase tracking-widest text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {docs.map((doc) => (
                <tr key={doc.id} className="transition-colors hover:bg-white/[0.025]">
                  <td className="px-6 py-3.5">
                    <Link href={`/documents/${doc.id}`} className="font-medium text-slate-200 hover:text-indigo-400 transition-colors">
                      {doc.title}
                    </Link>
                    <p className="text-xs text-slate-600">{doc.original_name}</p>
                  </td>
                  <td className="px-6 py-3.5">{statusBadge(doc.status)}</td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3.5 text-right">
                    <Button variant="ghost" size="xs" loading={unstarringId === doc.id} onClick={() => void handleUnstar(doc.id)}>
                      Unstar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-white/[0.05] px-6 py-3">
            <Button variant="glass" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</Button>
            <span className="text-xs text-slate-500">Page {page} of {totalPages}</span>
            <Button variant="glass" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        )}
      </Card>
    </div>
  );
}
