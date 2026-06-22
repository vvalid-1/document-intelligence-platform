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
    try {
      const r = await listDocuments(p, 20, true);
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
    if (!confirm('Restore this document to your active library?')) return;
    setRestoringId(id);
    try {
      await restoreDocument(id);
      await load(page, true);
    } catch {
      // ignore
    } finally {
      setRestoringId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Archived Documents</h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">{total} archived</p>
        </div>
        <Link href="/documents">
          <Button variant="secondary">← Active library</Button>
        </Link>
      </div>

      <Card padding={false}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : docs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-2xl mb-3">📦</p>
            <p className="font-medium text-gray-700 dark:text-slate-300">No archived documents</p>
            <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
              Archive documents from the{' '}
              <Link href="/documents" className="text-blue-600 hover:underline dark:text-blue-400">
                Documents page
              </Link>{' '}
              to keep them out of your active library.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs font-medium uppercase tracking-wide text-gray-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-6 py-3 text-left">Document</th>
                <th className="px-6 py-3 text-left">Type</th>
                <th className="px-6 py-3 text-left">Size</th>
                <th className="px-6 py-3 text-left">Archived</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50">
                  <td className="px-6 py-3">
                    <Link
                      href={`/documents/${doc.id}`}
                      className="font-medium text-gray-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400"
                    >
                      {doc.title}
                    </Link>
                    <p className="text-xs text-gray-400 dark:text-slate-500">{doc.original_name}</p>
                  </td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">
                    {doc.mime_type.split('/').pop()?.toUpperCase() ?? '—'}
                  </td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">
                    {doc.archived_at ? fmtDate(doc.archived_at) : '—'}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={restoringId === doc.id}
                      onClick={() => void handleRestore(doc.id)}
                    >
                      Restore
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
