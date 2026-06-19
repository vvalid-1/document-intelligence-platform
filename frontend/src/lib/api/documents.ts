import type { DocumentListResponse, DocumentResponse } from '@/types/api';
import { apiDelete, apiGet, apiRequest, getToken } from './client';

export function listDocuments(page = 1, pageSize = 20): Promise<DocumentListResponse> {
  return apiGet<DocumentListResponse>(`/documents/?page=${page}&page_size=${pageSize}`);
}

export function getDocument(id: string): Promise<DocumentResponse> {
  return apiGet<DocumentResponse>(`/documents/${id}`);
}

export function uploadDocument(file: File, title?: string): Promise<DocumentResponse> {
  const form = new FormData();
  form.append('file', file);
  if (title) form.append('title', title);
  return apiRequest<DocumentResponse>('/documents/', { method: 'POST', body: form });
}

export function deleteDocument(id: string): Promise<void> {
  return apiDelete<void>(`/documents/${id}`);
}

export async function downloadVersion(
  documentId: string,
  versionId: string,
  fmt: 'pdf' | 'txt',
  filename: string,
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(
    `/api/v1/documents/${documentId}/versions/${versionId}/download?fmt=${fmt}`,
    { headers },
  );

  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(body.detail ?? `Download failed (HTTP ${res.status})`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
