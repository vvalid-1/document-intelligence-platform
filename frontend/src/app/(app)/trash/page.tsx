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
    try {
      const r = await listDocuments(p, 20, { trashed: true });
      setDocs(r.items);
      setTotal(r.total);
    } catch {
      // ignore
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    void load(page);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  async function handleRestore(id: string) {
    setActionId(id);
    try {
      await untrashDocument(id);
      await load(page, true);
    } catch {
      // ignore
    } finally {
      setActionId(null);
    }
  }

  async function handlePermanentDelete(id: string) {
    if (!confirm('Permanently delete this document? This cannot be undone.')) return;
    setActionId(id);
    try {
      await permanentDeleteDocument(id);
      await load(page, true);
    } catch {
      // ignore
    } finally {
      setActionId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Trash</h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">{total} in trash</p>
        </div>
        <Link href="/documents">
          <Button variant="secondary">← Active library</Button>
        </Link>
      </div>

      {total > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
          Documents in trash can be restored or permanently deleted by an admin.
        </div>
      )}

      <Card padding={false}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : docs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-3xl mb-3">🗑</p>
            <p className="font-medium text-gray-700 dark:text-slate-300">Trash is empty</p>
            <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
              Deleted documents will appear here.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs font-medium uppercase tracking-wide text-gray-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-6 py-3 text-left">Document</th>
                <th className="px-6 py-3 text-left">Type</th>
                <th className="px-6 py-3 text-left">Size</th>
                <th className="px-6 py-3 text-left">Deleted</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                  <td className="px-6 py-3">
                    <p className="font-medium text-gray-900 dark:text-slate-100">{doc.title}</p>
                    <p className="text-xs text-gray-400 dark:text-slate-500">{doc.original_name}</p>
                  </td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">
                    {doc.mime_type.split('/').pop()?.toUpperCase() ?? '—'}
                  </td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">
                    {doc.deleted_at ? fmtDate(doc.deleted_at) : '—'}
                  </td>
                  <td className="px-6 py-3 text-right flex items-center justify-end gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={actionId === doc.id}
                      onClick={() => void handleRestore(doc.id)}
                    >
                      Restore
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      loading={actionId === doc.id}
                      onClick={() => void handlePermanentDelete(doc.id)}
                    >
                      Delete forever
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-100 px-6 py-3 dark:border-slate-700">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-sm text-gray-500 dark:text-slate-400">
              Page {page} of {totalPages}
            </span>
            <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
