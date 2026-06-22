'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listDocuments, permanentDeleteDocument, untrashDocument } from '@/lib/api/documents';
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

export default function TrashPage() {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);

  async function load(p: number, silent = false) {
    if (!silent) setLoading(true);
    try { const r = await listDocuments(p, 20, { trashed: true }); setDocs(r.items); setTotal(r.total); }
    catch { /* ignore */ } finally { if (!silent) setLoading(false); }
  }

  useEffect(() => { void load(page); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRestore(id: string) {
    setActionId(id);
    try { await untrashDocument(id); await load(page, true); } catch { /* ignore */ } finally { setActionId(null); }
  }

  async function handlePermanentDelete(id: string) {
    if (!confirm('Permanently delete this document? This cannot be undone.')) return;
    setActionId(id);
    try { await permanentDeleteDocument(id); await load(page, true); } catch { /* ignore */ } finally { setActionId(null); }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Trash</h1>
          <p className="mt-0.5 text-sm text-slate-500">{total} in trash</p>
        </div>
      </div>

      {total > 0 && (
        <div className="mb-4 flex items-center gap-2.5 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3 text-sm text-amber-400">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} className="shrink-0">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Documents in trash can be restored or permanently deleted by an admin.
        </div>
      )}

      <Card padding={false}>
        {loading ? (
          <div className="space-y-2 p-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-14 rounded-xl shimmer" />)}
          </div>
        ) : docs.length === 0 ? (
          <div className="py-20 text-center">
            <div className="mb-4 flex justify-center text-slate-700">
              <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <p className="text-slate-500">Trash is empty</p>
            <p className="mt-1 text-sm text-slate-600">Deleted documents will appear here.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.05]">
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Document</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Type</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Size</th>
                <th className="px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Deleted</th>
                <th className="px-6 py-3 text-right text-[11px] font-semibold uppercase tracking-widest text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {docs.map((doc) => (
                <tr key={doc.id} className="transition-colors hover:bg-white/[0.025]">
                  <td className="px-6 py-3.5">
                    <p className="font-medium text-slate-300">{doc.title}</p>
                    <p className="text-xs text-slate-600">{doc.original_name}</p>
                  </td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">
                    {doc.mime_type.split('/').pop()?.toUpperCase() ?? '—'}
                  </td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">
                    {doc.deleted_at ? fmtDate(doc.deleted_at) : '—'}
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button variant="glass" size="xs" loading={actionId === doc.id} onClick={() => void handleRestore(doc.id)}>
                        Restore
                      </Button>
                      <Button variant="danger" size="xs" loading={actionId === doc.id} onClick={() => void handlePermanentDelete(doc.id)}>
                        Delete forever
                      </Button>
                    </div>
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
