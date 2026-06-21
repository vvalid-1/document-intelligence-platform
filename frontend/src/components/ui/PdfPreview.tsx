'use client';

import { useEffect, useRef, useState } from 'react';
import { getToken } from '@/lib/api/client';

interface Props {
  documentId: string;
  className?: string;
}

export function PdfPreview({ documentId, className = '' }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [unsupported, setUnsupported] = useState(false);
  const [error, setError] = useState('');
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      setUnsupported(false);
      try {
        const token = getToken();
        const res = await fetch(`/api/v1/documents/${documentId}/download`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const ct = res.headers.get('content-type') ?? '';
        if (!ct.includes('pdf') && !ct.includes('text/plain')) {
          if (!cancelled) setUnsupported(true);
          return;
        }

        const blob = await res.blob();
        if (cancelled) return;

        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        setBlobUrl(url);
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Preview failed');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    };
  }, [documentId]);

  const base = `flex h-full w-full items-center justify-center bg-gray-50 ${className}`;

  if (loading) {
    return (
      <div className={base}>
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (unsupported) {
    return (
      <div className={base}>
        <p className="text-sm text-gray-400">Preview not available for this file type.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={base}>
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <iframe
      src={blobUrl ?? undefined}
      className={`h-full w-full border-0 bg-white ${className}`}
      title="Document preview"
    />
  );
}
