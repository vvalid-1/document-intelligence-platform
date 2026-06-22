'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  archiveDocument,
  bulkArchive,
  bulkFavorite,
  bulkMove,
  bulkTrash,
  deleteDocument,
  favoriteDocument,
  listDocuments,
  moveDocument,
  unfavoriteDocument,
} from '@/lib/api/documents';
import { listFolders } from '@/lib/api/folders';
import type { DocumentResponse, FolderResponse } from '@/types/api';
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
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [starringId, setStarringId] = useState<string | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);
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
      const opts: Parameters<typeof listDocuments>[2] = { favorite: tab === 'favorites' };
      if (selectedFolder) opts.folder_id = selectedFolder;
      const r = await listDocuments(p, 20, opts);
      setDocs(r.items);
      setTotal(r.total);
      setSelected(new Set());
      if (!r.items.some((d) => d.status === 'processing')) stopPoll();
    } catch {
      // ignore
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    void listFolders().then((r) => setFolders(r.items)).catch(() => {});
  }, []);

  useEffect(() => {
    void load(page);
    return () => stopPoll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, tab, selectedFolder]);

  useEffect(() => {
    stopPoll();
    if (docs.some((d) => d.status === 'processing')) {
      pollRef.current = setInterval(() => { void load(page, true); }, POLL_INTERVAL_MS);
    }
    return () => stopPoll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs, page]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected(selected.size === docs.length ? new Set() : new Set(docs.map((d) => d.id)));
  }

  async function handleDelete(id: string) {
    if (!confirm('Move this document to trash?')) return;
    setDeletingId(id);
    try { await deleteDocument(id); await load(page); } catch { /* ignore */ } finally { setDeletingId(null); }
  }

  async function handleArchive(id: string) {
    if (!confirm('Archive this document?')) return;
    setArchivingId(id);
    try { await archiveDocument(id); await load(page); } catch { /* ignore */ } finally { setArchivingId(null); }
  }

  async function handleStar(doc: DocumentResponse) {
    setStarringId(doc.id);
    try {
      if (doc.is_favorite) await unfavoriteDocument(doc.id); else await favoriteDocument(doc.id);
      await load(page, true);
    } catch { /* ignore */ } finally { setStarringId(null); }
  }

  async function handleMove(docId: string, folderId: string | null) {
    setMovingId(docId);
    try { await moveDocument(docId, folderId); await load(page, true); } catch { /* ignore */ } finally { setMovingId(null); }
  }

  async function handleBulkArchive() {
    if (!selected.size) return;
    setBulkLoading(true);
    try { await bulkArchive(Array.from(selected)); await load(page); } catch { /* ignore */ } finally { setBulkLoading(false); }
  }

  async function handleBulkTrash() {
    if (!selected.size || !confirm(`Move ${selected.size} document(s) to trash?`)) return;
    setBulkLoading(true);
    try { await bulkTrash(Array.from(selected)); await load(page); } catch { /* ignore */ } finally { setBulkLoading(false); }
  }

  async function handleBulkStar(value: boolean) {
    if (!selected.size) return;
    setBulkLoading(true);
    try { await bulkFavorite(Array.from(selected), value); await load(page, true); } catch { /* ignore */ } finally { setBulkLoading(false); }
  }

  async function handleBulkMove(folderId: string | null) {
    if (!selected.size) return;
    setBulkLoading(true);
    try { await bulkMove(Array.from(selected), folderId); await load(page, true); } catch { /* ignore */ } finally { setBulkLoading(false); }
  }

  const totalPages = Math.max(1, Math.ceil(total / 20));
  const allSelected = docs.length > 0 && selected.size === docs.length;
  const folderMap = Object.fromEntries(folders.map((f) => [f.id, f.name]));

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Documents</h1>
          <p className="mt-0.5 text-sm text-slate-500">{total} document{total !== 1 ? 's' : ''} total</p>
        </div>
        <Link href="/documents/upload">
          <Button size="md">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Upload
          </Button>
        </Link>
      </div>

      {/* Filter row */}
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex rounded-xl border border-white/[0.07] bg-white/[0.03] p-0.5">
          {(['all', 'favorites'] as FilterTab[]).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setPage(1); }}
              className={[
                'rounded-lg px-4 py-1.5 text-sm font-medium transition-all duration-200',
                tab === t
                  ? 'bg-indigo-500/20 text-indigo-300 shadow-sm'
                  : 'text-slate-500 hover:text-slate-300',
              ].join(' ')}
            >
              {t === 'all' ? 'All documents' : '★ Starred'}
            </button>
          ))}
        </div>

        {folders.length > 0 && (
          <select
            value={selectedFolder}
            onChange={(e) => { setSelectedFolder(e.target.value); setPage(1); }}
            className="rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-sm text-slate-300 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
          >
            <option value="">All folders</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-indigo-500/20 bg-indigo-500/[0.06] px-5 py-3">
          <span className="text-sm font-semibold text-indigo-300">
            {selected.size} selected
          </span>
          <div className="h-4 w-px bg-white/10" />
          <Button variant="secondary" size="sm" loading={bulkLoading} onClick={() => void handleBulkArchive()}>Archive</Button>
          <Button variant="secondary" size="sm" loading={bulkLoading} onClick={() => void handleBulkStar(true)}>Star</Button>
          <Button variant="secondary" size="sm" loading={bulkLoading} onClick={() => void handleBulkStar(false)}>Unstar</Button>
          {folders.length > 0 && (
            <select
              onChange={(e) => { void handleBulkMove(e.target.value || null); e.target.value = ''; }}
              defaultValue=""
              className="rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
            >
              <option value="" disabled>Move to folder…</option>
              <option value="">Remove from folder</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          )}
          <Button variant="danger" size="sm" loading={bulkLoading} onClick={() => void handleBulkTrash()}>Trash</Button>
          <button
            className="ml-auto text-xs text-slate-600 hover:text-slate-400 transition-colors"
            onClick={() => setSelected(new Set())}
          >
            Clear
          </button>
        </div>
      )}

      <Card padding={false}>
        {loading ? (
          <div className="space-y-2 p-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-14 rounded-xl shimmer" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="py-20 text-center">
            <div className="mb-4 flex justify-center text-slate-700">
              <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-slate-500">
              {tab === 'favorites' ? 'No starred documents.' : 'No documents found.'}
            </p>
            {tab === 'all' && !selectedFolder && (
              <Link href="/documents/upload" className="mt-2 inline-block text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
                Upload your first document →
              </Link>
            )}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.05]">
                <th className="px-4 py-3 text-left w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="cursor-pointer rounded accent-indigo-500"
                  />
                </th>
                <th className="px-3 py-3 w-8" />
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Document</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Status</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Size</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-slate-600">Pages</th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-widest text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {docs.map((doc) => (
                <tr
                  key={doc.id}
                  className={[
                    'transition-colors duration-150',
                    selected.has(doc.id)
                      ? 'bg-indigo-500/[0.06]'
                      : 'hover:bg-white/[0.025]',
                  ].join(' ')}
                >
                  <td className="px-4 py-3.5">
                    <input
                      type="checkbox"
                      checked={selected.has(doc.id)}
                      onChange={() => toggleSelect(doc.id)}
                      className="cursor-pointer rounded accent-indigo-500"
                    />
                  </td>
                  <td className="px-3 py-3.5">
                    <button
                      onClick={() => void handleStar(doc)}
                      disabled={starringId === doc.id}
                      className={[
                        'transition-all duration-200',
                        doc.is_favorite ? 'text-amber-400' : 'text-slate-700 hover:text-amber-400',
                      ].join(' ')}
                      title={doc.is_favorite ? 'Unstar' : 'Star'}
                    >
                      <svg width="14" height="14" fill={doc.is_favorite ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={doc.is_favorite ? 0 : 1.75}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                      </svg>
                    </button>
                  </td>
                  <td className="px-4 py-3.5">
                    <Link
                      href={`/documents/${doc.id}`}
                      className="font-medium text-slate-200 hover:text-indigo-400 transition-colors"
                    >
                      {doc.title}
                    </Link>
                    <div className="mt-0.5 flex items-center gap-2">
                      <p className="text-xs text-slate-600">{doc.original_name}</p>
                      {doc.folder_id && folderMap[doc.folder_id] && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-400">
                          {folderMap[doc.folder_id]}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3.5">{statusBadge(doc.status)}</td>
                  <td className="px-4 py-3.5 text-xs text-slate-500">{fileSize(doc.file_size_bytes)}</td>
                  <td className="px-4 py-3.5 text-xs text-slate-500">{doc.page_count ?? '—'}</td>
                  <td className="px-4 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Link href={`/documents/${doc.id}`}>
                        <Button variant="glass" size="xs">View</Button>
                      </Link>
                      {folders.length > 0 && (
                        <select
                          value={doc.folder_id ?? ''}
                          disabled={movingId === doc.id}
                          onChange={(e) => void handleMove(doc.id, e.target.value || null)}
                          className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-xs text-slate-400 focus:outline-none"
                        >
                          <option value="">No folder</option>
                          {folders.map((f) => (
                            <option key={f.id} value={f.id}>{f.name}</option>
                          ))}
                        </select>
                      )}
                      <Button variant="ghost" size="xs" loading={archivingId === doc.id} onClick={() => void handleArchive(doc.id)}>
                        Archive
                      </Button>
                      <Button variant="danger" size="xs" loading={deletingId === doc.id} onClick={() => void handleDelete(doc.id)}>
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
          <div className="flex items-center justify-between border-t border-white/[0.05] px-6 py-3">
            <Button variant="glass" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              ← Previous
            </Button>
            <span className="text-xs text-slate-500">
              Page {page} of {totalPages}
            </span>
            <Button variant="glass" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next →
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
