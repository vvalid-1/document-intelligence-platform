'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  archiveDocument,
  bulkArchive,
  bulkFavorite,
  bulkTrash,
  deleteDocument,
  favoriteDocument,
  listDocuments,
  unfavoriteDocument,
} from '@/lib/api/documents';
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

type FilterTab = 'all' | 'favorites';

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [starringId, setStarringId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [tab, setTab] = useState<FilterTab>('all');
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
      const r = await listDocuments(p, 20, { favorite: tab === 'favorites' });
      setDocs(r.items);
      setTotal(r.total);
      setSelected(new Set());
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
  }, [page, tab]);

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

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === docs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(docs.map((d) => d.id)));
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Move this document to trash?')) return;
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

  async function handleArchive(id: string) {
    if (!confirm('Archive this document? You can restore it later from the Archived page.')) return;
    setArchivingId(id);
    try {
      await archiveDocument(id);
      await load(page);
    } catch {
      // ignore
    } finally {
      setArchivingId(null);
    }
  }

  async function handleStar(doc: DocumentResponse) {
    setStarringId(doc.id);
    try {
      if (doc.is_favorite) {
        await unfavoriteDocument(doc.id);
      } else {
        await favoriteDocument(doc.id);
      }
      await load(page, true);
    } catch {
      // ignore
    } finally {
      setStarringId(null);
    }
  }

  async function handleBulkArchive() {
    if (selected.size === 0) return;
    setBulkLoading(true);
    try {
      await bulkArchive(Array.from(selected));
      await load(page);
    } catch {
      // ignore
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleBulkTrash() {
    if (selected.size === 0) return;
    if (!confirm(`Move ${selected.size} document(s) to trash?`)) return;
    setBulkLoading(true);
    try {
      await bulkTrash(Array.from(selected));
      await load(page);
    } catch {
      // ignore
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleBulkStar(value: boolean) {
    if (selected.size === 0) return;
    setBulkLoading(true);
    try {
      await bulkFavorite(Array.from(selected), value);
      await load(page, true);
    } catch {
      // ignore
    } finally {
      setBulkLoading(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));
  const allSelected = docs.length > 0 && selected.size === docs.length;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Documents</h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">{total} total</p>
        </div>
        <Link href="/documents/upload">
          <Button>Upload document</Button>
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1 border-b border-gray-200 dark:border-slate-700">
        {(['all', 'favorites'] as FilterTab[]).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setPage(1); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            {t === 'all' ? 'All' : '★ Starred'}
          </button>
        ))}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 dark:border-blue-800 dark:bg-blue-900/20">
          <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
            {selected.size} selected
          </span>
          <Button variant="secondary" size="sm" loading={bulkLoading} onClick={() => void handleBulkArchive()}>
            Archive
          </Button>
          <Button variant="secondary" size="sm" loading={bulkLoading} onClick={() => void handleBulkStar(true)}>
            Star
          </Button>
          <Button variant="secondary" size="sm" loading={bulkLoading} onClick={() => void handleBulkStar(false)}>
            Unstar
          </Button>
          <Button variant="danger" size="sm" loading={bulkLoading} onClick={() => void handleBulkTrash()}>
            Trash
          </Button>
          <button
            className="ml-auto text-xs text-gray-500 hover:text-gray-700 dark:text-slate-400"
            onClick={() => setSelected(new Set())}
          >
            Clear
          </button>
        </div>
      )}

      <Card padding={false}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : docs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-gray-500">
              {tab === 'favorites' ? 'No starred documents.' : 'No documents found.'}
            </p>
            {tab === 'all' && (
              <Link href="/documents/upload" className="mt-2 inline-block text-sm text-blue-600 hover:underline">
                Upload your first document →
              </Link>
            )}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs font-medium uppercase tracking-wide text-gray-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3 text-left w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="cursor-pointer rounded"
                  />
                </th>
                <th className="px-4 py-3 text-left w-8"></th>
                <th className="px-4 py-3 text-left">Document</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Size</th>
                <th className="px-4 py-3 text-left">Pages</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {docs.map((doc) => (
                <tr
                  key={doc.id}
                  className={`hover:bg-gray-50 dark:hover:bg-slate-700/50 ${selected.has(doc.id) ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(doc.id)}
                      onChange={() => toggleSelect(doc.id)}
                      className="cursor-pointer rounded"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => void handleStar(doc)}
                      disabled={starringId === doc.id}
                      className={`text-lg leading-none transition-colors ${
                        doc.is_favorite
                          ? 'text-amber-400 hover:text-amber-500'
                          : 'text-gray-300 hover:text-amber-400 dark:text-slate-600'
                      }`}
                      title={doc.is_favorite ? 'Unstar' : 'Star'}
                    >
                      ★
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/documents/${doc.id}`} className="font-medium text-gray-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400">
                      {doc.title}
                    </Link>
                    <p className="text-xs text-gray-400 dark:text-slate-500">{doc.original_name}</p>
                  </td>
                  <td className="px-4 py-3">{statusBadge(doc.status)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-slate-400">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-slate-400">{doc.page_count ?? '—'}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link href={`/documents/${doc.id}`}>
                        <Button variant="ghost" size="sm">View</Button>
                      </Link>
                      <Button
                        variant="secondary"
                        size="sm"
                        loading={archivingId === doc.id}
                        onClick={() => void handleArchive(doc.id)}
                      >
                        Archive
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        loading={deletingId === doc.id}
                        onClick={() => void handleDelete(doc.id)}
                      >
                        Trash
                      </Button>
                    </div>
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
