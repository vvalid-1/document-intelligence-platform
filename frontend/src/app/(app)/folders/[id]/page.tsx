'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { listFolderDocuments, listFolders } from '@/lib/api/folders';
import { moveDocument } from '@/lib/api/documents';
import type { DocumentListResponse, FolderResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { statusBadge } from '@/components/ui/Badge';

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function FolderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [folder, setFolder] = useState<FolderResponse | null>(null);
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState<string | null>(null);

  async function load(p: number, silent = false) {
    if (!silent) setLoading(true);
    try {
      const [folderList, docs] = await Promise.all([
        listFolders(),
        listFolderDocuments(id, p),
      ]);
      setFolder(folderList.items.find((f) => f.id === id) ?? null);
      setData(docs);
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

  async function handleRemove(docId: string) {
    setRemovingId(docId);
    try {
      await moveDocument(docId, null);
      await load(page, true);
    } catch {
      // ignore
    } finally {
      setRemovingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href="/folders" className="text-sm text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200">
              Folders
            </Link>
            <span className="text-gray-300 dark:text-slate-600">/</span>
            <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">
              {folder?.name ?? '…'}
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-slate-400">{data?.total ?? 0} documents</p>
        </div>
        <Link href="/documents">
          <Button variant="secondary">← All Documents</Button>
        </Link>
      </div>

      <Card padding={false}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-3xl mb-3">📁</p>
            <p className="font-medium text-gray-700 dark:text-slate-300">This folder is empty</p>
            <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
              Move documents here from the{' '}
              <Link href="/documents" className="text-blue-600 hover:underline dark:text-blue-400">
                Documents page
              </Link>.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs font-medium uppercase tracking-wide text-gray-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-6 py-3 text-left">Document</th>
                <th className="px-6 py-3 text-left">Status</th>
                <th className="px-6 py-3 text-left">Size</th>
                <th className="px-6 py-3 text-left">Pages</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {data.items.map((doc) => (
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
                  <td className="px-6 py-3">{statusBadge(doc.status)}</td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-6 py-3 text-gray-500 dark:text-slate-400">{doc.page_count ?? '—'}</td>
                  <td className="px-6 py-3 text-right flex items-center justify-end gap-2">
                    <Link href={`/documents/${doc.id}`}>
                      <Button variant="ghost" size="sm">View</Button>
                    </Link>
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={removingId === doc.id}
                      onClick={() => void handleRemove(doc.id)}
                    >
                      Remove
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
