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
import { Card, CardHeader } from '@/components/ui/Card';

// A4 at 72 DPI — matches PyMuPDF default
const PAGE_W = 595;
const PAGE_H = 842;
const SCALE = 0.5;

type DrawMode = 'typed' | 'draw' | 'upload';

const MODE_LABELS: Record<DrawMode, string> = {
  typed: 'Typed',
  draw: 'Draw',
  upload: 'Upload PNG',
};

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
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setImageB64(dataUrl.split(',')[1] ?? '');
    };
    reader.readAsDataURL(file);
  }

  function handleModeChange(mode: DrawMode) {
    setDrawMode(mode);
    setError('');
  }

  async function handleSign() {
    setLoading(true);
    setError('');
    try {
      let image_base64: string | null = null;
      const signature_type = drawMode === 'typed' ? 'typed' : 'drawn';

      if (drawMode === 'draw') {
        image_base64 = canvasRef.current?.toBase64() ?? null;
        if (!image_base64) {
          setError('Please draw your signature first.');
          setLoading(false);
          return;
        }
      } else if (drawMode === 'upload') {
        image_base64 = imageB64;
        if (!image_base64) {
          setError('Please select a signature image.');
          setLoading(false);
          return;
        }
      }

      const r = await signDocument(id, {
        signature_type,
        typed_text: drawMode === 'typed' ? typedText || null : null,
        image_base64,
        x,
        y,
        page_number: pageNumber,
        field_name: fieldName || null,
      });
      setResult(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Signing failed');
    } finally {
      setLoading(false);
    }
  }

  const isDisabled =
    drawMode === 'typed' ? !typedText.trim() :
    drawMode === 'draw' ? !hasDrawn :
    !imageB64;

  const markerLeft = Math.min(Math.max(x * SCALE, 0), PAGE_W * SCALE - 8);
  const markerTop = Math.min(Math.max(y * SCALE, 0), PAGE_H * SCALE - 8);

  return (
    <div className="flex h-full">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-gray-100 lg:flex lg:flex-col dark:border-slate-700">
        <div className="border-b border-gray-100 bg-white px-4 py-2.5 dark:bg-slate-800 dark:border-slate-700">
          <span className="text-xs font-medium text-gray-500 dark:text-slate-400">Document preview</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Sign panel */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="sm">←</Button>
          </Link>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Sign document</h1>
        </div>

        <div className="flex flex-col gap-6 lg:flex-row">
          {/* Controls */}
          <div className="flex-1 space-y-5">
            <Card>
              <CardHeader title="Signature type" />
              <div className="flex gap-2">
                {(['typed', 'draw', 'upload'] as DrawMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => handleModeChange(mode)}
                    className={`flex-1 rounded-lg border px-3 py-2.5 text-sm font-medium transition-all ${
                      drawMode === mode
                        ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-500'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50 dark:border-slate-600 dark:text-slate-400 dark:hover:border-slate-500 dark:hover:bg-slate-700'
                    }`}
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
                    <label className="mb-2 block text-sm font-medium text-gray-800 dark:text-slate-300">
                      Draw your signature
                    </label>
                    <SignatureCanvas ref={canvasRef} onChange={setHasDrawn} />
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-2"
                      onClick={() => {
                        canvasRef.current?.clear();
                        setHasDrawn(false);
                      }}
                    >
                      Clear
                    </Button>
                  </div>
                )}
                {drawMode === 'upload' && (
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-800 dark:text-slate-300">
                      Signature image (PNG)
                    </label>
                    <input
                      type="file"
                      accept="image/png"
                      onChange={handleImagePick}
                      className="block w-full text-sm text-gray-500 file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
                    />
                    {imageB64 && (
                      <p className="mt-1.5 text-xs font-medium text-emerald-600">✓ Image loaded</p>
                    )}
                  </div>
                )}
              </div>
            </Card>

            <Card>
              <CardHeader title="Position" subtitle="Click the page grid or enter coordinates" />
              <div className="grid grid-cols-3 gap-3">
                <Input
                  label="X (pt)"
                  type="number"
                  value={x}
                  onChange={(e) => setX(Number(e.target.value))}
                  min={0}
                  max={590}
                />
                <Input
                  label="Y (pt)"
                  type="number"
                  value={y}
                  onChange={(e) => setY(Number(e.target.value))}
                  min={0}
                  max={837}
                />
                <Input
                  label="Page"
                  type="number"
                  value={pageNumber}
                  onChange={(e) => setPageNumber(Number(e.target.value))}
                  min={1}
                />
              </div>
              <p className="mt-2 text-xs text-gray-400">
                Coordinates in points. A4: 595 × 842 pt.
              </p>
            </Card>

            <Card>
              <CardHeader title="Field name" subtitle="Optional label for this signature" />
              <Input
                value={fieldName}
                onChange={(e) => setFieldName(e.target.value)}
                placeholder="e.g. Approver, Witness"
                maxLength={255}
              />
            </Card>

            {error && (
              <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                {error}
              </p>
            )}

            <Button
              className="w-full"
              size="lg"
              loading={loading}
              disabled={isDisabled}
              onClick={() => void handleSign()}
            >
              Apply signature
            </Button>

            {result && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-sm font-semibold text-emerald-800">Signature applied</p>
                <p className="mt-1 text-xs text-emerald-600">
                  Version {result.version_number} created · Page {result.page_number}
                </p>
                <Link
                  href={`/documents/${id}`}
                  className="mt-2 inline-block text-xs font-medium text-emerald-700 hover:underline"
                >
                  View document →
                </Link>
              </div>
            )}
          </div>

          {/* Coordinate grid — click to place */}
          <div className="shrink-0">
            <p className="mb-2 text-sm font-medium text-gray-700 dark:text-slate-300">Click to place on page</p>
            <div
              ref={previewRef}
              onClick={handlePreviewClick}
              className="relative cursor-crosshair overflow-hidden rounded-xl border-2 border-dashed border-gray-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-600"
              style={{ width: PAGE_W * SCALE, height: PAGE_H * SCALE }}
            >
              <div className="absolute inset-0 opacity-10">
                {Array.from({ length: 20 }).map((_, i) => (
                  <div
                    key={i}
                    className="absolute border-t border-gray-400"
                    style={{ top: (i + 1) * (PAGE_H * SCALE / 21), left: 0, right: 0 }}
                  />
                ))}
              </div>

              <div
                className="pointer-events-none absolute flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center"
                style={{ left: markerLeft, top: markerTop }}
              >
                <div className="h-3 w-3 rounded-full bg-blue-600 opacity-80 ring-2 ring-blue-300" />
              </div>

              {drawMode === 'typed' && typedText && (
                <div
                  className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded text-[10px] font-medium text-blue-800"
                  style={{ left: markerLeft, top: markerTop + 10 }}
                >
                  {typedText}
                </div>
              )}

              <p className="absolute bottom-2 left-0 right-0 text-center text-[9px] text-gray-300 dark:text-slate-600">
                A4 · {PAGE_W} × {PAGE_H} pt · Click to place
              </p>
            </div>
            <p className="mt-1.5 text-xs text-gray-400 dark:text-slate-500">x={x}, y={y}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
