'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { translateDocument } from '@/lib/api/translations';
import { downloadVersion } from '@/lib/api/documents';
import type { TranslationLanguage, TranslationResponse } from '@/types/api';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';

const LANGUAGES: { code: TranslationLanguage; label: string; native: string; flag: string }[] = [
  { code: 'en', label: 'English', native: 'English', flag: '🇬🇧' },
  { code: 'fr', label: 'French', native: 'Français', flag: '🇫🇷' },
  { code: 'ar', label: 'Arabic', native: 'العربية', flag: '🇸🇦' },
];

export default function TranslatePage() {
  const { id } = useParams<{ id: string }>();
  const [targetLanguage, setTargetLanguage] = useState<TranslationLanguage>('fr');
  const [result, setResult] = useState<TranslationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadingFmt, setDownloadingFmt] = useState<'pdf' | 'txt' | null>(null);

  async function handleTranslate() {
    setLoading(true); setError('');
    try { const r = await translateDocument(id, targetLanguage); setResult(r); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Translation failed'); }
    finally { setLoading(false); }
  }

  async function handleDownload(fmt: 'pdf' | 'txt') {
    if (!result) return;
    setDownloadingFmt(fmt);
    try { await downloadVersion(id, result.id, fmt, `v${result.version_number}_${result.target_language}.${fmt}`); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Download failed'); }
    finally { setDownloadingFmt(null); }
  }

  const selectedLang = LANGUAGES.find((l) => l.code === targetLanguage);

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

      {/* Translate panel */}
      <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
        <div className="mb-6 flex items-center gap-3">
          <Link href={`/documents/${id}`} className="lg:hidden">
            <Button variant="ghost" size="xs">← Back</Button>
          </Link>
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">Translate document</h1>
        </div>

        <div className="mx-auto max-w-2xl space-y-5">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6">
            <div className="mb-5">
              <p className="text-sm font-semibold text-slate-100">Target language</p>
              <p className="mt-0.5 text-xs text-slate-500">Select the language to translate into</p>
            </div>

            <div className="flex gap-3">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => setTargetLanguage(lang.code)}
                  className={[
                    'flex-1 rounded-2xl border p-4 text-center transition-all duration-200',
                    targetLanguage === lang.code
                      ? 'border-emerald-500/40 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.1)]'
                      : 'border-white/[0.07] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]',
                  ].join(' ')}
                >
                  <p className="text-xl mb-1">{lang.flag}</p>
                  <p className={`text-sm font-semibold ${targetLanguage === lang.code ? 'text-emerald-300' : 'text-slate-200'}`}>
                    {lang.label}
                  </p>
                  <p className={`mt-0.5 text-xs ${targetLanguage === lang.code ? 'text-emerald-500' : 'text-slate-600'}`}>
                    {lang.native}
                  </p>
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

            <Button className="mt-5 w-full" size="lg" loading={loading} onClick={() => void handleTranslate()}>
              {loading ? 'Translating…' : `Translate to ${selectedLang?.label ?? ''}`}
            </Button>
            {loading && <p className="mt-2 text-center text-xs text-slate-600">This may take 30–120 seconds on CPU</p>}
          </div>

          {result && (
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/[0.04] p-6 animate-fade-in">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-100">Version {result.version_number} — {result.language_name}</p>
                  {result.change_summary && <p className="text-xs text-slate-500">{result.change_summary}</p>}
                </div>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Preview</p>
                <p
                  className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300"
                  dir={result.target_language === 'ar' ? 'rtl' : 'ltr'}
                  lang={result.target_language}
                >
                  {result.text_preview}
                </p>
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
