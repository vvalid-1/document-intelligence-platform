'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { createFolder, deleteFolder, listFolders, renameFolder } from '@/lib/api/folders';
import type { FolderResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

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
    try {
      const r = await listFolders();
      setFolders(r.items);
    } catch {
      // ignore
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    setError('');
    try {
      await createFolder(newName.trim());
      setNewName('');
      setShowCreate(false);
      await load(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create folder');
    } finally {
      setCreating(false);
    }
  }

  async function handleRename(id: string) {
    if (!renameValue.trim()) return;
    setActionId(id);
    setError('');
    try {
      await renameFolder(id, renameValue.trim());
      setRenamingId(null);
      setRenameValue('');
      await load(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to rename folder');
    } finally {
      setActionId(null);
    }
  }

  async function handleDelete(folder: FolderResponse) {
    if (!confirm(`Delete folder "${folder.name}"? Documents will remain but will be unassigned.`)) return;
    setActionId(folder.id);
    try {
      await deleteFolder(folder.id);
      await load(true);
    } catch {
      // ignore
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Folders</h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-slate-400">{folders.length} folder{folders.length !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={() => { setShowCreate(true); setError(''); }}>New folder</Button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-slate-700 dark:bg-slate-800">
          <p className="mb-2 text-sm font-medium text-gray-700 dark:text-slate-300">New folder name</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
              placeholder="e.g. Scholarship Projects"
              autoFocus
              className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <Button size="sm" loading={creating} onClick={() => void handleCreate()}>Create</Button>
            <Button size="sm" variant="ghost" onClick={() => { setShowCreate(false); setNewName(''); setError(''); }}>Cancel</Button>
          </div>
          {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        </div>
      ) : folders.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-3xl mb-3">📁</p>
          <p className="font-medium text-gray-700 dark:text-slate-300">No folders yet</p>
          <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
            Create a folder to organise your documents.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {folders.map((folder) => (
            <Card key={folder.id}>
              {renamingId === folder.id ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && void handleRename(folder.id)}
                    autoFocus
                    className="w-full rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                  />
                  {error && <p className="text-xs text-red-600">{error}</p>}
                  <div className="flex gap-2">
                    <Button size="sm" loading={actionId === folder.id} onClick={() => void handleRename(folder.id)}>Save</Button>
                    <Button size="sm" variant="ghost" onClick={() => { setRenamingId(null); setRenameValue(''); setError(''); }}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <>
                  <Link href={`/folders/${folder.id}`} className="block group">
                    <div className="flex items-center gap-3 mb-3">
                      <span className="text-2xl">📁</span>
                      <p className="font-semibold text-gray-900 group-hover:text-blue-600 dark:text-slate-100 dark:group-hover:text-blue-400 truncate">
                        {folder.name}
                      </p>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-slate-400">
                      {folder.doc_count} document{folder.doc_count !== 1 ? 's' : ''}
                    </p>
                  </Link>
                  <div className="mt-4 flex gap-2 border-t border-gray-100 pt-3 dark:border-slate-700">
                    <button
                      onClick={() => { setRenamingId(folder.id); setRenameValue(folder.name); setError(''); }}
                      className="text-xs text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200"
                    >
                      Rename
                    </button>
                    <span className="text-gray-300 dark:text-slate-600">·</span>
                    <button
                      onClick={() => void handleDelete(folder)}
                      disabled={actionId === folder.id}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
