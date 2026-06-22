import type { DocumentListResponse, DocumentResponse, DocumentStatsResponse, DocumentVersionListItem } from '@/types/api';
import { apiDelete, apiGet, apiPost, apiRequest, getToken } from './client';

export function listDocuments(page = 1, pageSize = 20, archived = false): Promise<DocumentListResponse> {
  const base = `/documents?page=${page}&page_size=${pageSize}`;
  return apiGet<DocumentListResponse>(archived ? `${base}&archived=true` : base);
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

export function archiveDocument(id: string): Promise<DocumentResponse> {
  return apiPost<DocumentResponse>(`/documents/${id}/archive`);
}

export function restoreDocument(id: string): Promise<DocumentResponse> {
  return apiPost<DocumentResponse>(`/documents/${id}/restore`);
}

export function getDocumentStats(): Promise<DocumentStatsResponse> {
  return apiGet<DocumentStatsResponse>('/documents/stats');
}

export function listVersions(documentId: string): Promise<DocumentVersionListItem[]> {
  return apiGet<DocumentVersionListItem[]>(`/documents/${documentId}/versions`);
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
