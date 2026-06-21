'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { translateDocument } from '@/lib/api/translations';
import { downloadVersion } from '@/lib/api/documents';
import type { TranslationLanguage, TranslationResponse } from '@/types/api';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';

const LANGUAGES: { code: TranslationLanguage; label: string; native: string }[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'fr', label: 'French', native: 'Français' },
  { code: 'ar', label: 'Arabic', native: 'العربية' },
];

export default function TranslatePage() {
  const { id } = useParams<{ id: string }>();
  const [targetLanguage, setTargetLanguage] = useState<TranslationLanguage>('fr');
  const [result, setResult] = useState<TranslationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadingFmt, setDownloadingFmt] = useState<'pdf' | 'txt' | null>(null);

  async function handleTranslate() {
    setLoading(true);
    setError('');
    try {
      const r = await translateDocument(id, targetLanguage);
      setResult(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Translation failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload(fmt: 'pdf' | 'txt') {
    if (!result) return;
    setDownloadingFmt(fmt);
    try {
      const baseName = result.document_id.slice(0, 8);
      await downloadVersion(
        id,
        result.id,
        fmt,
        `v${result.version_number}_${result.target_language}.${fmt}`,
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setDownloadingFmt(null);
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

      {/* Translate panel */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="sm">←</Button>
          </Link>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Translate document</h1>
        </div>

        <div className="mx-auto max-w-2xl space-y-6">
          <Card>
            <CardHeader
              title="Target language"
              subtitle="Select the language to translate the document into"
            />
            <div className="flex gap-3">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => setTargetLanguage(lang.code)}
                  className={`flex-1 rounded-xl border px-4 py-3 text-center transition-all ${
                    targetLanguage === lang.code
                      ? 'border-blue-500 bg-blue-50 shadow-sm dark:bg-blue-900/30 dark:border-blue-500'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 dark:border-slate-600 dark:hover:border-slate-500 dark:hover:bg-slate-700'
                  }`}
                >
                  <p className={`text-sm font-semibold ${targetLanguage === lang.code ? 'text-blue-700 dark:text-blue-300' : 'text-gray-800 dark:text-slate-200'}`}>
                    {lang.label}
                  </p>
                  <p className={`mt-0.5 text-xs ${targetLanguage === lang.code ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500 dark:text-slate-400'}`}>
                    {lang.native}
                  </p>
                </button>
              ))}
            </div>

            {error && (
              <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                {error}
              </p>
            )}

            <Button
              className="mt-5 w-full"
              loading={loading}
              onClick={() => void handleTranslate()}
            >
              Translate to {LANGUAGES.find((l) => l.code === targetLanguage)?.label}
            </Button>
            {loading && (
              <p className="mt-2 text-center text-xs text-gray-400 dark:text-slate-500">
                AI is translating your document — this may take 30–120 seconds…
              </p>
            )}
          </Card>

          {result && (
            <Card>
              <CardHeader
                title={`Version ${result.version_number} — ${result.language_name}`}
                subtitle={result.change_summary}
              />
              <div className="rounded-lg bg-gray-50 p-4 dark:bg-slate-700">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-slate-400">
                  Preview (first 500 chars)
                </p>
                <p
                  className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800 dark:text-slate-100"
                  dir={result.target_language === 'ar' ? 'rtl' : 'ltr'}
                >
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
