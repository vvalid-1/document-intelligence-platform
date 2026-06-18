'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { listDocuments, deleteDocument } from '@/lib/api/documents';
import type { DocumentResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { statusBadge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

const POLL_INTERVAL_MS = 2000;

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPoll() {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function load(p: number, silent = false) {
    if (!silent) setLoading(true);
    try {
      const r = await listDocuments(p, 20);
      setDocs(r.items);
      setTotal(r.total);
      const anyProcessing = r.items.some((d) => d.status === 'processing');
      if (!anyProcessing) stopPoll();
    } catch {
      // ignore
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    void load(page);
    return () => stopPoll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => {
    stopPoll();
    const anyProcessing = docs.some((d) => d.status === 'processing');
    if (anyProcessing) {
      pollRef.current = setInterval(() => {
        void load(page, true);
      }, POLL_INTERVAL_MS);
    }
    return () => stopPoll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs, page]);

  async function handleDelete(id: string) {
    if (!confirm('Delete this document?')) return;
    setDeletingId(id);
    try {
      await deleteDocument(id);
      await load(page);
    } catch {
      // ignore
    } finally {
      setDeletingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Documents</h1>
          <p className="mt-0.5 text-sm text-gray-500">{total} total</p>
        </div>
        <Link href="/documents/upload">
          <Button>Upload document</Button>
        </Link>
      </div>

      <Card padding={false}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : docs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-gray-500">No documents found.</p>
            <Link href="/documents/upload" className="mt-2 inline-block text-sm text-blue-600 hover:underline">
              Upload your first document →
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs font-medium uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-6 py-3 text-left">Document</th>
                <th className="px-6 py-3 text-left">Status</th>
                <th className="px-6 py-3 text-left">Size</th>
                <th className="px-6 py-3 text-left">Pages</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-3">
                    <Link href={`/documents/${doc.id}`} className="font-medium text-gray-900 hover:text-blue-600">
                      {doc.title}
                    </Link>
                    <p className="text-xs text-gray-400">{doc.original_name}</p>
                  </td>
                  <td className="px-6 py-3">{statusBadge(doc.status)}</td>
                  <td className="px-6 py-3 text-gray-500">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3 text-gray-500">{doc.page_count ?? '—'}</td>
                  <td className="px-6 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link href={`/documents/${doc.id}`}>
                        <Button variant="ghost" size="sm">View</Button>
                      </Link>
                      <Button
                        variant="danger"
                        size="sm"
                        loading={deletingId === doc.id}
                        onClick={() => void handleDelete(doc.id)}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-100 px-6 py-3">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-sm text-gray-500">
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
