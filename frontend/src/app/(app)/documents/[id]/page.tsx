'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { getDocument } from '@/lib/api/documents';
import { listSignatures } from '@/lib/api/signatures';
import type { DocumentResponse, SignatureResponse } from '@/types/api';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { statusBadge } from '@/components/ui/Badge';

function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleString();
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [sigs, setSigs] = useState<SignatureResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDocument(id), listSignatures(id)])
      .then(([d, s]) => {
        setDoc(d);
        setSigs(s.items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!doc) {
    return <div className="p-8 text-gray-500">Document not found.</div>;
  }

  const actions = [
    { href: `/documents/${id}/chat`, label: 'Chat', desc: 'Ask questions about this document' },
    { href: `/documents/${id}/review`, label: 'Review', desc: 'AI quality review and suggestions' },
    { href: `/documents/${id}/edit`, label: 'Edit', desc: 'Natural language editing' },
    { href: `/documents/${id}/sign`, label: 'Sign', desc: 'Add electronic signature' },
  ];

  return (
    <div className="p-8">
      <div className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{doc.title}</h1>
          <p className="mt-0.5 text-sm text-gray-500">{doc.original_name}</p>
        </div>
        {statusBadge(doc.status)}
      </div>

      <div className="mb-6 flex gap-2">
        <Link href="/documents">
          <Button variant="ghost" size="sm">← Back</Button>
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader title="Document info" />
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {[
                ['File name', doc.original_name],
                ['Type', doc.mime_type],
                ['Size', fileSize(doc.file_size_bytes)],
                ['Pages', doc.page_count ?? '—'],
                ['Chunks', doc.chunk_count],
                ['Uploaded', fmtDate(doc.created_at)],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt className="text-gray-500">{k}</dt>
                  <dd className="font-medium text-gray-900">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          {sigs.length > 0 && (
            <Card>
              <CardHeader
                title="Signatures"
                subtitle={`${sigs.length} signature${sigs.length !== 1 ? 's' : ''}`}
              />
              <ul className="space-y-2">
                {sigs.map((s) => (
                  <li key={s.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium capitalize">{s.signature_type}</p>
                      <p className="text-xs text-gray-500">
                        Page {s.page_number} · x={s.position_data.x?.toFixed(0)}, y={s.position_data.y?.toFixed(0)}
                        {s.version_number != null && ` · v${s.version_number}`}
                      </p>
                    </div>
                    <span className="text-xs text-gray-400">{fmtDate(s.signed_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div>
          <Card>
            <CardHeader title="AI actions" />
            <div className="space-y-2">
              {actions.map(({ href, label, desc }) => (
                <Link
                  key={href}
                  href={doc.status === 'ready' ? href : '#'}
                  className={`block rounded-lg border border-gray-200 p-3 transition-colors ${doc.status === 'ready' ? 'hover:border-blue-300 hover:bg-blue-50' : 'cursor-not-allowed opacity-50'}`}
                >
                  <p className="text-sm font-medium text-gray-900">{label}</p>
                  <p className="text-xs text-gray-500">{desc}</p>
                </Link>
              ))}
              {doc.status !== 'ready' && (
                <p className="text-xs text-gray-400">Actions are available once the document is ready.</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
