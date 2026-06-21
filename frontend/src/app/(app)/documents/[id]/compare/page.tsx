'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { getDocumentText, getVersionText } from '@/lib/api/compare';
import { listVersions } from '@/lib/api/documents';
import { diffLines, diffStats, toSideBySide } from '@/lib/diff';
import type { DiffEntry, SideLine } from '@/lib/diff';
import type { DocumentVersionListItem } from '@/types/api';
import { Button } from '@/components/ui/Button';

type ViewMode = 'side-by-side' | 'unified';

const LINE_CLS: Record<string, string> = {
  equal: 'bg-white dark:bg-slate-900',
  add: 'bg-emerald-50 dark:bg-emerald-900/20',
  remove: 'bg-red-50 dark:bg-red-900/20',
  empty: 'bg-gray-50 dark:bg-slate-800',
};

const GUTTER_CLS: Record<string, string> = {
  equal: 'text-gray-400 bg-gray-50 dark:bg-slate-800 dark:text-slate-500',
  add: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400',
  remove: 'text-red-500 bg-red-100 dark:bg-red-900/30 dark:text-red-400',
  empty: 'bg-gray-100 dark:bg-slate-700',
};

function LineRow({ line, side }: { line: SideLine; side: 'left' | 'right' }) {
  const type = line.type;
  if (type === 'empty') {
    return (
      <div className="flex min-h-[1.5rem] border-b border-gray-100 dark:border-slate-700/50">
        <div className={`w-12 shrink-0 select-none border-r border-gray-200 px-2 text-right text-xs leading-6 dark:border-slate-700 ${GUTTER_CLS.empty}`} />
        <div className={`flex-1 px-3 py-0 text-sm leading-6 ${LINE_CLS.empty}`} />
      </div>
    );
  }
  const prefix = type === 'add' ? '+' : type === 'remove' ? '−' : ' ';
  return (
    <div className={`flex min-h-[1.5rem] border-b border-gray-100 dark:border-slate-700/50 ${LINE_CLS[type]}`}>
      <div className={`w-12 shrink-0 select-none border-r border-gray-200 px-2 text-right text-xs leading-6 dark:border-slate-700 ${GUTTER_CLS[type]}`}>
        {line.lineNum ?? ''}
      </div>
      <div className="w-5 shrink-0 select-none text-center text-xs leading-6 font-mono opacity-60">
        {prefix}
      </div>
      <pre className="flex-1 overflow-x-auto whitespace-pre-wrap break-words px-2 py-0 font-mono text-xs leading-6 text-gray-800 dark:text-slate-200">
        {line.text || ' '}
      </pre>
    </div>
  );
}

function UnifiedLine({ entry, leftNum, rightNum }: { entry: DiffEntry; leftNum: number | null; rightNum: number | null }) {
  const type = entry.type;
  const prefix = type === 'add' ? '+' : type === 'remove' ? '−' : ' ';
  return (
    <div className={`flex min-h-[1.5rem] border-b border-gray-100 dark:border-slate-700/50 ${LINE_CLS[type]}`}>
      <div className={`w-10 shrink-0 select-none border-r border-gray-200 px-1.5 text-right text-xs leading-6 dark:border-slate-700 ${GUTTER_CLS[type]}`}>
        {leftNum ?? ''}
      </div>
      <div className={`w-10 shrink-0 select-none border-r border-gray-200 px-1.5 text-right text-xs leading-6 dark:border-slate-700 ${GUTTER_CLS[type]}`}>
        {rightNum ?? ''}
      </div>
      <div className="w-5 shrink-0 select-none text-center text-xs leading-6 font-mono opacity-60">
        {prefix}
      </div>
      <pre className="flex-1 overflow-x-auto whitespace-pre-wrap break-words px-2 py-0 font-mono text-xs leading-6 text-gray-800 dark:text-slate-200">
        {entry.text || ' '}
      </pre>
    </div>
  );
}

export default function ComparePage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const aParam = searchParams.get('a') ?? 'original';
  const bParam = searchParams.get('b') ?? '';

  const [viewMode, setViewMode] = useState<ViewMode>('side-by-side');
  const [versions, setVersions] = useState<DocumentVersionListItem[]>([]);
  const [leftText, setLeftText] = useState('');
  const [rightText, setRightText] = useState('');
  const [leftLabel, setLeftLabel] = useState('Original');
  const [rightLabel, setRightLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const leftScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);
  const syncingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const vers = await listVersions(id);
        if (cancelled) return;
        setVersions(vers);

        // Load left side
        let left = '';
        if (aParam === 'original') {
          const res = await getDocumentText(id);
          left = res.text;
          setLeftLabel('Original document');
        } else {
          left = await getVersionText(id, aParam);
          const v = vers.find((x) => x.id === aParam);
          setLeftLabel(v ? `v${v.version_number} (${v.agent_name ?? 'unknown'})` : `Version ${aParam.slice(0, 8)}`);
        }

        // Load right side
        let right = '';
        if (bParam) {
          right = await getVersionText(id, bParam);
          const v = vers.find((x) => x.id === bParam);
          setRightLabel(v ? `v${v.version_number} (${v.agent_name ?? 'unknown'})` : `Version ${bParam.slice(0, 8)}`);
        }

        if (cancelled) return;
        setLeftText(left);
        setRightText(right);
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load comparison');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [id, aParam, bParam]);

  // Synchronized scroll
  function onLeftScroll() {
    if (syncingRef.current || !rightScrollRef.current || !leftScrollRef.current) return;
    syncingRef.current = true;
    const pct = leftScrollRef.current.scrollTop / (leftScrollRef.current.scrollHeight - leftScrollRef.current.clientHeight || 1);
    rightScrollRef.current.scrollTop = pct * (rightScrollRef.current.scrollHeight - rightScrollRef.current.clientHeight);
    syncingRef.current = false;
  }

  function onRightScroll() {
    if (syncingRef.current || !leftScrollRef.current || !rightScrollRef.current) return;
    syncingRef.current = true;
    const pct = rightScrollRef.current.scrollTop / (rightScrollRef.current.scrollHeight - rightScrollRef.current.clientHeight || 1);
    leftScrollRef.current.scrollTop = pct * (leftScrollRef.current.scrollHeight - leftScrollRef.current.clientHeight);
    syncingRef.current = false;
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center gap-3">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        <span className="text-sm text-gray-500 dark:text-slate-400">Loading comparison…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 px-6 py-4 dark:border-red-800 dark:bg-red-900/20">
          <p className="text-sm font-medium text-red-700 dark:text-red-400">Failed to load comparison</p>
          <p className="mt-1 text-xs text-red-600 dark:text-red-300">{error}</p>
          <Link href={`/documents/${id}`} className="mt-3 inline-block text-xs font-medium text-red-700 hover:underline dark:text-red-400">← Back to document</Link>
        </div>
      </div>
    );
  }

  if (!bParam) {
    return (
      <div className="p-8">
        <div className="mb-4 flex items-center gap-3">
          <Link href={`/documents/${id}`}><Button variant="ghost" size="sm">←</Button></Link>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Compare versions</h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-6">Select a version to compare against the original:</p>
        <div className="space-y-2 max-w-lg">
          {versions
            .filter((v) => v.agent_name === 'editor' || v.agent_name === 'translator')
            .map((v) => (
              <Link
                key={v.id}
                href={`/documents/${id}/compare?a=original&b=${v.id}`}
                className="flex items-center justify-between rounded-lg border border-gray-200 p-3 hover:border-blue-300 hover:bg-blue-50 transition-colors dark:border-slate-700 dark:hover:border-blue-500 dark:hover:bg-blue-900/20"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-slate-100">
                    Version {v.version_number}
                    <span className="ml-2 text-xs font-normal capitalize text-gray-500 dark:text-slate-400">({v.agent_name})</span>
                  </p>
                  {v.change_summary && <p className="text-xs text-gray-500 dark:text-slate-400">{v.change_summary}</p>}
                </div>
                <span className="text-xs text-blue-600 dark:text-blue-400">Compare →</span>
              </Link>
            ))}
          {versions.filter((v) => v.agent_name === 'editor' || v.agent_name === 'translator').length === 0 && (
            <p className="text-sm text-gray-400 dark:text-slate-500">No edited or translated versions yet.</p>
          )}
        </div>
      </div>
    );
  }

  const entries = diffLines(leftText, rightText);
  const stats = diffStats(entries);
  const { left: leftLines, right: rightLines } = toSideBySide(entries);

  // Build unified view with line numbers
  let leftCount = 0;
  let rightCount = 0;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-3 dark:bg-slate-800 dark:border-slate-700">
        <Link href={`/documents/${id}`}>
          <Button variant="ghost" size="sm">←</Button>
        </Link>
        <h1 className="flex-1 text-sm font-semibold text-gray-900 dark:text-slate-100">
          Compare: {leftLabel} → {rightLabel}
        </h1>
        <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-slate-400">
          <span className="rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">+{stats.added}</span>
          <span className="rounded px-1.5 py-0.5 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">−{stats.removed}</span>
          <span className="rounded px-1.5 py-0.5 bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-300">{stats.equal} equal</span>
        </div>
        <div className="flex rounded-lg border border-gray-200 overflow-hidden dark:border-slate-600">
          {(['side-by-side', 'unified'] as ViewMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors capitalize ${
                viewMode === m
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700'
              }`}
            >
              {m === 'side-by-side' ? 'Side by side' : 'Unified'}
            </button>
          ))}
        </div>
      </div>

      {/* Diff body */}
      {viewMode === 'side-by-side' ? (
        <div className="flex flex-1 overflow-hidden">
          {/* Left panel */}
          <div className="flex w-1/2 flex-col border-r border-gray-200 dark:border-slate-700">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 dark:bg-slate-800 dark:border-slate-700">
              <span className="text-xs font-semibold text-gray-700 dark:text-slate-300">{leftLabel}</span>
            </div>
            <div
              ref={leftScrollRef}
              onScroll={onLeftScroll}
              className="flex-1 overflow-auto"
            >
              {leftLines.map((line, i) => (
                <LineRow key={i} line={line} side="left" />
              ))}
            </div>
          </div>
          {/* Right panel */}
          <div className="flex w-1/2 flex-col">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 dark:bg-slate-800 dark:border-slate-700">
              <span className="text-xs font-semibold text-gray-700 dark:text-slate-300">{rightLabel}</span>
            </div>
            <div
              ref={rightScrollRef}
              onScroll={onRightScroll}
              className="flex-1 overflow-auto"
            >
              {rightLines.map((line, i) => (
                <LineRow key={i} line={line} side="right" />
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 dark:bg-slate-800 dark:border-slate-700 flex gap-8">
            <span className="w-10 text-right text-xs font-semibold text-gray-500 dark:text-slate-400">Old</span>
            <span className="w-10 text-right text-xs font-semibold text-gray-500 dark:text-slate-400">New</span>
          </div>
          {entries.map((entry, i) => {
            const ln = entry.type === 'remove' ? ++leftCount : entry.type === 'add' ? null : (++leftCount, leftCount);
            const rn = entry.type === 'add' ? ++rightCount : entry.type === 'remove' ? null : (++rightCount, rightCount);
            return (
              <UnifiedLine key={i} entry={entry} leftNum={entry.type === 'add' ? null : ln} rightNum={entry.type === 'remove' ? null : rn} />
            );
          })}
        </div>
      )}
    </div>
  );
}
