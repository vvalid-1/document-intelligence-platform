'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listDocuments } from '@/lib/api/documents';
import type { DocumentResponse } from '@/types/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { statusBadge } from '@/components/ui/Badge';

function fmt(n: number, unit: string) {
  return `${n} ${unit}${n !== 1 ? 's' : ''}`;
}

export default function DashboardPage() {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDocuments(1, 5)
      .then((r) => setDocs(r.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const ready = docs.filter((d) => d.status === 'ready').length;
  const processing = docs.filter((d) => d.status === 'processing').length;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Dashboard</h1>
        <Link href="/documents/upload">
          <Button>Upload document</Button>
        </Link>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-4">
        {[
          { label: 'Total documents', value: docs.length, sub: 'loaded (first 5)' },
          { label: 'Ready', value: ready, sub: 'available for AI' },
          { label: 'Processing', value: processing, sub: 'being indexed' },
        ].map(({ label, value, sub }) => (
          <Card key={label}>
            <p className="text-sm text-gray-500">{label}</p>
            <p className="mt-1 text-3xl font-bold text-gray-900">{loading ? '—' : value}</p>
            <p className="mt-1 text-xs text-gray-400">{sub}</p>
          </Card>
        ))}
      </div>

      <Card padding={false}>
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 className="text-sm font-semibold text-gray-900">Recent documents</h2>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : docs.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm text-gray-500">No documents yet.</p>
            <Link href="/documents/upload" className="mt-2 inline-block text-sm text-blue-600 hover:underline">
              Upload your first document
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {docs.map((doc) => (
              <li key={doc.id}>
                <Link href={`/documents/${doc.id}`} className="flex items-center justify-between px-6 py-3 hover:bg-gray-50">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">{doc.title}</p>
                    <p className="text-xs text-gray-400">{doc.original_name}</p>
                  </div>
                  <div className="ml-4 flex shrink-0 items-center gap-3">
                    {statusBadge(doc.status)}
                    <span className="text-xs text-gray-400">
                      {fmt(doc.page_count ?? 0, 'page')}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {docs.length > 0 && (
          <div className="border-t border-gray-100 px-6 py-3">
            <Link href="/documents" className="text-sm text-blue-600 hover:underline">
              View all documents →
            </Link>
          </div>
        )}
      </Card>
    </div>
  );
}
