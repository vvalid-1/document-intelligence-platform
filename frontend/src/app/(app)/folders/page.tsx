'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { createFolder, deleteFolder, listFolders, renameFolder } from '@/lib/api/folders';
import type { FolderResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';

export default function FoldersPage() {
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState('');

  async function load(silent = false) {
    if (!silent) setLoading(true);
    try { const r = await listFolders(); setFolders(r.items); } catch { /* ignore */ }
    finally { if (!silent) setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true); setError('');
    try { await createFolder(newName.trim()); setNewName(''); setShowCreate(false); await load(true); }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to create folder'); }
    finally { setCreating(false); }
  }

  async function handleRename(id: string) {
    if (!renameValue.trim()) return;
    setActionId(id); setError('');
    try { await renameFolder(id, renameValue.trim()); setRenamingId(null); setRenameValue(''); await load(true); }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to rename folder'); }
    finally { setActionId(null); }
  }

  async function handleDelete(folder: FolderResponse) {
    if (!confirm(`Delete folder "${folder.name}"? Documents will remain but will be unassigned.`)) return;
    setActionId(folder.id);
    try { await deleteFolder(folder.id); await load(true); } catch { /* ignore */ } finally { setActionId(null); }
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Folders</h1>
          <p className="mt-0.5 text-sm text-slate-500">{folders.length} folder{folders.length !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={() => { setShowCreate(true); setError(''); }}>
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New folder
        </Button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
          <p className="mb-3 text-sm font-medium text-slate-300">New folder name</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
              placeholder="e.g. Scholarship Projects"
              autoFocus
              className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/40"
            />
            <Button size="sm" loading={creating} onClick={() => void handleCreate()}>Create</Button>
            <Button size="sm" variant="ghost" onClick={() => { setShowCreate(false); setNewName(''); setError(''); }}>Cancel</Button>
          </div>
          {error && <p className="mt-1.5 text-xs text-rose-400">{error}</p>}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-28 rounded-2xl shimmer" />)}
        </div>
      ) : folders.length === 0 ? (
        <div className="py-20 text-center">
          <div className="mb-4 flex justify-center text-slate-700">
            <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 7a2 2 0 012-2h3.586a1 1 0 01.707.293L11 7h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </div>
          <p className="font-medium text-slate-400">No folders yet</p>
          <p className="mt-1 text-sm text-slate-600">Create a folder to organise your documents.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {folders.map((folder) => (
            <div
              key={folder.id}
              className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5 transition-all duration-200 hover:border-white/[0.12] hover:bg-white/[0.05]"
            >
              {renamingId === folder.id ? (
                <div className="space-y-3">
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && void handleRename(folder.id)}
                    autoFocus
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-sm text-slate-100 focus:border-indigo-500/50 focus:outline-none"
                  />
                  {error && <p className="text-xs text-rose-400">{error}</p>}
                  <div className="flex gap-2">
                    <Button size="xs" loading={actionId === folder.id} onClick={() => void handleRename(folder.id)}>Save</Button>
                    <Button size="xs" variant="ghost" onClick={() => { setRenamingId(null); setRenameValue(''); setError(''); }}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <>
                  <Link href={`/folders/${folder.id}`} className="block group">
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-2xl bg-sky-500/10 text-sky-400">
                      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7a2 2 0 012-2h3.586a1 1 0 01.707.293L11 7h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
                      </svg>
                    </div>
                    <p className="font-semibold text-slate-200 group-hover:text-white transition-colors truncate">
                      {folder.name}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {folder.doc_count} document{folder.doc_count !== 1 ? 's' : ''}
                    </p>
                  </Link>
                  <div className="mt-4 flex gap-2 border-t border-white/[0.05] pt-3">
                    <button
                      onClick={() => { setRenamingId(folder.id); setRenameValue(folder.name); setError(''); }}
                      className="text-xs text-slate-600 hover:text-slate-300 transition-colors"
                    >
                      Rename
                    </button>
                    <span className="text-slate-800">·</span>
                    <button
                      onClick={() => void handleDelete(folder)}
                      disabled={actionId === folder.id}
                      className="text-xs text-rose-600 hover:text-rose-400 transition-colors disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
