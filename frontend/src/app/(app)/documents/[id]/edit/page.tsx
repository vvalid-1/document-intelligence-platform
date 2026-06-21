'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { editDocument } from '@/lib/api/edits';
import { downloadVersion } from '@/lib/api/documents';
import type { EditResponse } from '@/types/api';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Input';
import { Card, CardHeader } from '@/components/ui/Card';

const EXAMPLES = [
  'Fix all grammar and spelling errors',
  'Make the tone more formal and professional',
  'Add an executive summary at the beginning',
  'Remove any redundant paragraphs',
];

export default function EditPage() {
  const { id } = useParams<{ id: string }>();
  const [instruction, setInstruction] = useState('');
  const [result, setResult] = useState<EditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadingFmt, setDownloadingFmt] = useState<'pdf' | 'txt' | null>(null);

  async function handleDownload(fmt: 'pdf' | 'txt') {
    if (!result) return;
    setDownloadingFmt(fmt);
    try {
      const baseName = result.document_id.slice(0, 8);
      await downloadVersion(id, result.id, fmt, `v${result.version_number}_${baseName}.${fmt}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setDownloadingFmt(null);
    }
  }

  async function handleEdit() {
    if (!instruction.trim()) return;
    setLoading(true);
    setError('');
    try {
      const r = await editDocument(id, instruction.trim());
      setResult(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Edit failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-gray-200 lg:flex lg:flex-col dark:border-slate-700">
        <div className="border-b border-gray-200 bg-white px-4 py-2 dark:bg-slate-800 dark:border-slate-700">
          <span className="text-xs font-medium text-gray-500 dark:text-slate-400">Document preview</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Edit panel */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="sm">←</Button>
          </Link>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Edit document</h1>
        </div>

        <div className="mx-auto max-w-2xl space-y-6">
          <Card>
            <CardHeader
              title="Edit instruction"
              subtitle="Describe what changes you want the AI to make"
            />
            <div className="space-y-4">
              <Textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="e.g. Fix grammar errors and improve clarity"
                rows={4}
                maxLength={2000}
              />
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setInstruction(ex)}
                    className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-slate-600 dark:text-slate-400 dark:hover:border-blue-500 dark:hover:bg-blue-900/20 dark:hover:text-blue-400"
                  >
                    {ex}
                  </button>
                ))}
              </div>
              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
              )}
              <Button
                className="w-full"
                loading={loading}
                disabled={!instruction.trim()}
                onClick={() => void handleEdit()}
              >
                Apply edit
              </Button>
              {loading && (
                <p className="text-center text-xs text-gray-400">
                  AI is rewriting your document — this may take 30–120 seconds…
                </p>
              )}
            </div>
          </Card>

          {result && (
            <Card>
              <CardHeader
                title={`Version ${result.version_number} created`}
                subtitle={result.change_summary}
              />
              <div className="rounded-lg bg-gray-50 p-4 dark:bg-slate-700">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-slate-400">
                  Preview (first 500 chars)
                </p>
                <p className="whitespace-pre-wrap text-sm text-gray-800 leading-relaxed dark:text-slate-100">
                  {result.text_preview}
                </p>
              </div>
              <div className="mt-4 flex gap-3">
                <Button
                  variant="secondary"
                  size="sm"
                  loading={downloadingFmt === 'pdf'}
                  disabled={downloadingFmt !== null}
                  onClick={() => void handleDownload('pdf')}
                >
                  Download PDF
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  loading={downloadingFmt === 'txt'}
                  disabled={downloadingFmt !== null}
                  onClick={() => void handleDownload('txt')}
                >
                  Download TXT
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
