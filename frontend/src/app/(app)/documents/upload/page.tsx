'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadDocument } from '@/lib/api/documents';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader } from '@/components/ui/Card';

const ACCEPTED = '.pdf,.docx,.txt,.jpg,.jpeg,.png';
const MAX_MB = 50;

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
    <div className="p-8">
      <h1 className="mb-6 text-xl font-bold text-gray-900 dark:text-slate-100">Upload document</h1>

      <div className="mx-auto max-w-lg">
        <Card>
          <CardHeader title="Select a file" subtitle="PDF, DOCX, TXT, JPG, or PNG — max 50 MB" />

          <form onSubmit={handleSubmit} className="space-y-5">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 transition-colors ${dragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 hover:border-gray-400 dark:border-slate-600 dark:hover:border-slate-500'}`}
            >
              {file ? (
                <div className="text-center">
                  <p className="font-medium text-gray-900 dark:text-slate-100">{file.name}</p>
                  <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="mt-2 text-sm text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <>
                  <p className="text-sm text-gray-500 dark:text-slate-400">Drag and drop here, or</p>
                  <label className="mt-2 cursor-pointer text-sm font-medium text-blue-600 hover:underline">
                    browse files
                    <input
                      type="file"
                      accept={ACCEPTED}
                      className="hidden"
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); }}
                    />
                  </label>
                  <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">PDF · DOCX · TXT · JPG · PNG</p>
                </>
              )}
            </div>

            <Input
              label="Title (optional)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My document"
            />

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
            )}

            <Button type="submit" className="w-full" loading={uploading} disabled={!file}>
              Upload and process
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
