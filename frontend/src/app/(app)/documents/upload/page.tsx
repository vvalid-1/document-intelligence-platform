'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadDocument } from '@/lib/api/documents';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

const ACCEPTED = '.pdf,.docx,.txt,.jpg,.jpeg,.png,.mp3,.wav,.mp4';
const MAX_MB = 50;

const FILE_TYPES = [
  { ext: 'PDF', color: 'text-rose-400 bg-rose-500/10' },
  { ext: 'DOCX', color: 'text-blue-400 bg-blue-500/10' },
  { ext: 'TXT', color: 'text-slate-400 bg-slate-500/10' },
  { ext: 'JPG', color: 'text-amber-400 bg-amber-500/10' },
  { ext: 'PNG', color: 'text-green-400 bg-green-500/10' },
  { ext: 'MP3', color: 'text-violet-400 bg-violet-500/10' },
  { ext: 'WAV', color: 'text-indigo-400 bg-indigo-500/10' },
  { ext: 'MP4', color: 'text-pink-400 bg-pink-500/10' },
];

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (['mp3', 'wav'].includes(ext)) return (
    <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25} className="text-violet-400">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
    </svg>
  );
  if (ext === 'mp4') return (
    <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25} className="text-pink-400">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  );
  if (['jpg', 'jpeg', 'png'].includes(ext)) return (
    <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25} className="text-amber-400">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
  return (
    <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25} className="text-indigo-400">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  function pickFile(f: File) {
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File must be under ${MAX_MB} MB`);
      return;
    }
    setFile(f);
    setError('');
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''));
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) pickFile(f);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const doc = await uploadDocument(file, title || undefined);
      router.push(`/documents/${doc.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-start justify-center p-8 pt-16">
      <div className="w-full max-w-xl animate-fade-in">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-[0_0_40px_rgba(99,102,241,0.4)]">
            <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Upload document</h1>
          <p className="mt-1 text-sm text-slate-500">Add a file to your intelligence workspace</p>
        </div>

        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-8 shadow-[0_8px_40px_rgba(0,0,0,0.4)] backdrop-blur-xl">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={[
                'relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-8 py-12 text-center transition-all duration-300',
                dragging
                  ? 'border-indigo-500/60 bg-indigo-500/[0.06] shadow-[0_0_40px_rgba(99,102,241,0.15)]'
                  : file
                  ? 'border-emerald-500/40 bg-emerald-500/[0.04]'
                  : 'border-white/[0.1] hover:border-white/[0.2] hover:bg-white/[0.02]',
              ].join(' ')}
            >
              {file ? (
                <div className="flex flex-col items-center gap-3">
                  {fileIcon(file.name)}
                  <div>
                    <p className="font-semibold text-slate-100">{file.name}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setFile(null); setTitle(''); }}
                    className="text-xs text-rose-400 hover:text-rose-300 transition-colors"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.05] text-slate-500">
                    <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">
                      Drag and drop your file here, or{' '}
                      <label className="cursor-pointer font-semibold text-indigo-400 hover:text-indigo-300 transition-colors">
                        browse
                        <input
                          type="file"
                          accept={ACCEPTED}
                          className="hidden"
                          onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); }}
                        />
                      </label>
                    </p>
                    <p className="mt-1 text-xs text-slate-700">Max {MAX_MB} MB</p>
                  </div>
                </div>
              )}
            </div>

            {/* File type pills */}
            <div className="flex flex-wrap gap-1.5 justify-center">
              {FILE_TYPES.map(({ ext, color }) => (
                <span key={ext} className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${color}`}>
                  {ext}
                </span>
              ))}
            </div>

            <Input
              label="Title"
              value={title}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
              placeholder="Document title (optional)"
              hint="Leave blank to use the filename"
            />

            {error && (
              <div className="flex items-center gap-2.5 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3">
                <svg width="16" height="16" className="shrink-0 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm text-rose-400">{error}</p>
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" loading={uploading} disabled={!file}>
              {uploading ? 'Processing upload…' : 'Upload and analyze'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
