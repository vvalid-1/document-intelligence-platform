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
      await downloadVersion(id, result.id, fmt, `v${result.version_number}_${result.document_id.slice(0, 8)}.${fmt}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally { setDownloadingFmt(null); }
  }

  async function handleEdit() {
    if (!instruction.trim()) return;
    setLoading(true); setError('');
    try { const r = await editDocument(id, instruction.trim()); setResult(r); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Edit failed'); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex h-full bg-[#0a0f1e]">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-white/[0.06] lg:flex lg:flex-col">
        <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-4 py-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="xs">
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </Button>
          </Link>
          <span className="text-xs text-slate-600">Document preview</span>
          <div className="w-16" />
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Edit panel */}
      <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`} className="lg:hidden">
            <Button variant="ghost" size="xs">← Back</Button>
          </Link>
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/10 text-sky-400">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">Edit document</h1>
        </div>

        <div className="mx-auto max-w-2xl space-y-5">
          {/* Instruction input */}
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6">
            <div className="mb-4">
              <p className="text-sm font-semibold text-slate-100">Edit instruction</p>
              <p className="mt-0.5 text-xs text-slate-500">Describe what changes you want the AI to make</p>
            </div>
            <Textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="e.g. Fix grammar errors and improve clarity throughout the document"
              rows={4}
              maxLength={2000}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setInstruction(ex)}
                  className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-xs text-slate-400 transition-all hover:border-indigo-500/30 hover:bg-indigo-500/[0.06] hover:text-indigo-300"
                >
                  {ex}
                </button>
              ))}
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                {error}
              </div>
            )}

            <Button className="mt-5 w-full" size="lg" loading={loading} disabled={!instruction.trim()} onClick={() => void handleEdit()}>
              {loading ? 'AI is rewriting your document…' : 'Apply edit'}
            </Button>
            {loading && <p className="mt-2 text-center text-xs text-slate-600">This may take 30–120 seconds on CPU</p>}
          </div>

          {result && (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.04] p-6 animate-fade-in">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-100">Version {result.version_number} created</p>
                  {result.change_summary && <p className="text-xs text-slate-500">{result.change_summary}</p>}
                </div>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Preview</p>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{result.text_preview}</p>
              </div>
              <div className="mt-4 flex gap-2">
                <Button variant="glass" size="sm" loading={downloadingFmt === 'pdf'} disabled={downloadingFmt !== null} onClick={() => void handleDownload('pdf')}>
                  Download PDF
                </Button>
                <Button variant="glass" size="sm" loading={downloadingFmt === 'txt'} disabled={downloadingFmt !== null} onClick={() => void handleDownload('txt')}>
                  Download TXT
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
