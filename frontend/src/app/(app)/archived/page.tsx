'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listDocuments, restoreDocument } from '@/lib/api/documents';
import type { DocumentResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString();
}

export default function ArchivedPage() {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  async function load(p: number, silent = false) {
    if (!silent) setLoading(true);
    try { const r = await listDocuments(p, 20, { archived: true }); setDocs(r.items); setTotal(r.total); }
    catch { /* ignore */ } finally { if (!silent) setLoading(false); }
  }

  useEffect(() => { void load(page); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRestore(id: string) {
    if (!confirm('Restore this document to your active library?')) return;
    setRestoringId(id);
    try { await restoreDocument(id); await load(page, true); } catch { /* ignore */ } finally { setRestoringId(null); }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Archived</h1>
          <p className="mt-0.5 text-sm text-slate-500">{total} archived document{total !== 1 ? 's' : ''}</p>
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
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
              </svg>
            </div>
            <p className="text-slate-500">No archived documents</p>
            <p className="mt-1 text-sm text-slate-600">
              Archive documents from the{' '}
              <Link href="/documents" className="text-indigo-400 hover:text-indigo-300 transition-colors">Documents page</Link>{' '}
              to keep them out of your active library.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.05]">
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Document</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Type</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Size</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Archived</th>
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
                  <td className="px-6 py-3.5 text-xs text-slate-500">{doc.mime_type.split('/').pop()?.toUpperCase() ?? '—'}</td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">{doc.archived_at ? fmtDate(doc.archived_at) : '—'}</td>
                  <td className="px-6 py-3.5 text-right">
                    <Button variant="glass" size="xs" loading={restoringId === doc.id} onClick={() => void handleRestore(doc.id)}>
                      Restore
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
