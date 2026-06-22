'use client';

import { useCallback, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { signDocument } from '@/lib/api/signatures';
import type { SignatureResponse } from '@/types/api';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { SignatureCanvas } from '@/components/ui/SignatureCanvas';
import type { SignatureCanvasHandle } from '@/components/ui/SignatureCanvas';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

const PAGE_W = 595;
const PAGE_H = 842;
const SCALE = 0.5;

type DrawMode = 'typed' | 'draw' | 'upload';
const MODE_LABELS: Record<DrawMode, string> = { typed: 'Typed', draw: 'Draw', upload: 'Upload PNG' };

export default function SignPage() {
  const { id } = useParams<{ id: string }>();
  const [drawMode, setDrawMode] = useState<DrawMode>('typed');
  const [typedText, setTypedText] = useState('');
  const [x, setX] = useState(100);
  const [y, setY] = useState(700);
  const [pageNumber, setPageNumber] = useState(1);
  const [fieldName, setFieldName] = useState('');
  const [imageB64, setImageB64] = useState<string | null>(null);
  const [hasDrawn, setHasDrawn] = useState(false);
  const [result, setResult] = useState<SignatureResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const canvasRef = useRef<SignatureCanvasHandle>(null);
  const previewRef = useRef<HTMLDivElement>(null);

  const handlePreviewClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setX(Math.round((e.clientX - rect.left) / SCALE));
    setY(Math.round((e.clientY - rect.top) / SCALE));
  }, []);

  function handleImagePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setImageB64((reader.result as string).split(',')[1] ?? ''); };
    reader.readAsDataURL(file);
  }

  async function handleSign() {
    setLoading(true); setError('');
    try {
      let image_base64: string | null = null;
      const signature_type = drawMode === 'typed' ? 'typed' : 'drawn';
      if (drawMode === 'draw') {
        image_base64 = canvasRef.current?.toBase64() ?? null;
        if (!image_base64) { setError('Please draw your signature first.'); setLoading(false); return; }
      } else if (drawMode === 'upload') {
        image_base64 = imageB64;
        if (!image_base64) { setError('Please select a signature image.'); setLoading(false); return; }
      }
      const r = await signDocument(id, {
        signature_type, typed_text: drawMode === 'typed' ? typedText || null : null,
        image_base64, x, y, page_number: pageNumber, field_name: fieldName || null,
      });
      setResult(r);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Signing failed'); }
    finally { setLoading(false); }
  }

  const isDisabled = drawMode === 'typed' ? !typedText.trim() : drawMode === 'draw' ? !hasDrawn : !imageB64;
  const markerLeft = Math.min(Math.max(x * SCALE, 0), PAGE_W * SCALE - 8);
  const markerTop = Math.min(Math.max(y * SCALE, 0), PAGE_H * SCALE - 8);

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

      {/* Sign panel */}
      <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`} className="lg:hidden">
            <Button variant="ghost" size="xs">← Back</Button>
          </Link>
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-pink-500/10 text-pink-400">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">Sign document</h1>
        </div>

        <div className="flex flex-col gap-5 lg:flex-row">
          {/* Controls */}
          <div className="flex-1 space-y-4">
            {/* Signature type */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
              <p className="mb-3 text-sm font-semibold text-slate-100">Signature type</p>
              <div className="flex gap-2">
                {(['typed', 'draw', 'upload'] as DrawMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => { setDrawMode(mode); setError(''); }}
                    className={[
                      'flex-1 rounded-xl border px-3 py-2.5 text-sm font-medium transition-all duration-200',
                      drawMode === mode
                        ? 'border-pink-500/40 bg-pink-500/[0.08] text-pink-300 shadow-[0_0_16px_rgba(236,72,153,0.1)]'
                        : 'border-white/[0.07] text-slate-500 hover:border-white/[0.12] hover:text-slate-300',
                    ].join(' ')}
                  >
                    {MODE_LABELS[mode]}
                  </button>
                ))}
              </div>

              <div className="mt-4">
                {drawMode === 'typed' && (
                  <Input
                    label="Signature text"
                    value={typedText}
                    onChange={(e) => setTypedText(e.target.value)}
                    placeholder="Your full name"
                    maxLength={200}
                  />
                )}
                {drawMode === 'draw' && (
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-slate-600">Draw your signature</p>
                    <SignatureCanvas ref={canvasRef} onChange={setHasDrawn} />
                    <Button variant="ghost" size="sm" className="mt-2" onClick={() => { canvasRef.current?.clear(); setHasDrawn(false); }}>
                      Clear
                    </Button>
                  </div>
                )}
                {drawMode === 'upload' && (
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-slate-600">Signature image (PNG)</p>
                    <input
                      type="file"
                      accept="image/png"
                      onChange={handleImagePick}
                      className="block w-full text-sm text-slate-500 file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-indigo-500/10 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-indigo-300 hover:file:bg-indigo-500/20"
                    />
                    {imageB64 && (
                      <p className="mt-1.5 flex items-center gap-1.5 text-xs text-emerald-400">
                        <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        Image loaded
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Position */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
              <p className="mb-0.5 text-sm font-semibold text-slate-100">Position</p>
              <p className="mb-4 text-xs text-slate-600">Click the page grid or enter coordinates</p>
              <div className="grid grid-cols-3 gap-3">
                <Input label="X (pt)" type="number" value={x} onChange={(e) => setX(Number(e.target.value))} min={0} max={590} />
                <Input label="Y (pt)" type="number" value={y} onChange={(e) => setY(Number(e.target.value))} min={0} max={837} />
                <Input label="Page" type="number" value={pageNumber} onChange={(e) => setPageNumber(Number(e.target.value))} min={1} />
              </div>
              <p className="mt-2 text-xs text-slate-700">Coordinates in points. A4: 595 × 842 pt.</p>
            </div>

            {/* Field name */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
              <p className="mb-0.5 text-sm font-semibold text-slate-100">Field name</p>
              <p className="mb-3 text-xs text-slate-600">Optional label for this signature</p>
              <Input value={fieldName} onChange={(e) => setFieldName(e.target.value)} placeholder="e.g. Approver, Witness" maxLength={255} />
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="shrink-0">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                {error}
              </div>
            )}

            <Button className="w-full" size="lg" loading={loading} disabled={isDisabled} onClick={() => void handleSign()}>
              Apply signature
            </Button>

            {result && (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.05] p-5 animate-fade-in">
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                    <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="text-sm font-semibold text-emerald-300">Signature applied</p>
                </div>
                <p className="text-xs text-emerald-600">Version {result.version_number} created · Page {result.page_number}</p>
                <Link href={`/documents/${id}`} className="mt-3 inline-block text-xs font-medium text-emerald-400 hover:text-emerald-300 transition-colors">
                  View document →
                </Link>
              </div>
            )}
          </div>

          {/* Coordinate grid — click to place */}
          <div className="shrink-0">
            <p className="mb-2 text-sm font-medium text-slate-400">Click to place on page</p>
            <div
              ref={previewRef}
              onClick={handlePreviewClick}
              className="relative cursor-crosshair overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.02]"
              style={{ width: PAGE_W * SCALE, height: PAGE_H * SCALE }}
            >
              <div className="absolute inset-0 opacity-[0.04]">
                {Array.from({ length: 20 }).map((_, i) => (
                  <div key={i} className="absolute border-t border-slate-400" style={{ top: (i + 1) * (PAGE_H * SCALE / 21), left: 0, right: 0 }} />
                ))}
              </div>
              <div
                className="pointer-events-none absolute flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center"
                style={{ left: markerLeft, top: markerTop }}
              >
                <div className="h-3 w-3 rounded-full bg-indigo-500 opacity-90 ring-2 ring-indigo-300/40" />
              </div>
              {drawMode === 'typed' && typedText && (
                <div
                  className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded text-[10px] font-medium text-indigo-300"
                  style={{ left: markerLeft, top: markerTop + 10 }}
                >
                  {typedText}
                </div>
              )}
              <p className="absolute bottom-2 left-0 right-0 text-center text-[9px] text-slate-700">
                A4 · {PAGE_W} × {PAGE_H} pt · Click to place
              </p>
            </div>
            <p className="mt-1.5 text-xs text-slate-700">x={x}, y={y}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
