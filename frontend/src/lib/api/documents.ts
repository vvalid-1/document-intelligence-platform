import type { DocumentListResponse, DocumentResponse, DocumentStatsResponse, DocumentVersionListItem } from '@/types/api';
import { apiDelete, apiGet, apiPost, apiRequest, getToken } from './client';

type ListDocumentsOpts = { archived?: boolean; favorite?: boolean; trashed?: boolean; folder_id?: string };

export function listDocuments(page = 1, pageSize = 20, opts: ListDocumentsOpts = {}): Promise<DocumentListResponse> {
  const base = `/documents?page=${page}&page_size=${pageSize}`;
  const params: string[] = [];
  if (opts.archived) params.push('archived=true');
  if (opts.favorite) params.push('favorite=true');
  if (opts.trashed) params.push('trashed=true');
  if (opts.folder_id) params.push(`folder_id=${opts.folder_id}`);
  return apiGet<DocumentListResponse>(params.length ? `${base}&${params.join('&')}` : base);
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

export function favoriteDocument(id: string): Promise<DocumentResponse> {
  return apiPost<DocumentResponse>(`/documents/${id}/favorite`);
}

export function unfavoriteDocument(id: string): Promise<DocumentResponse> {
  return apiPost<DocumentResponse>(`/documents/${id}/unfavorite`);
}

export function untrashDocument(id: string): Promise<DocumentResponse> {
  return apiPost<DocumentResponse>(`/documents/${id}/untrash`);
}

export function permanentDeleteDocument(id: string): Promise<void> {
  return apiDelete<void>(`/documents/${id}/permanent`);
}

export function bulkArchive(ids: string[]): Promise<void> {
  return apiPost<void>('/documents/bulk/archive', { ids });
}

export function bulkRestore(ids: string[]): Promise<void> {
  return apiPost<void>('/documents/bulk/restore', { ids });
}

export function bulkTrash(ids: string[]): Promise<void> {
  return apiPost<void>('/documents/bulk/trash', { ids });
}

export function bulkFavorite(ids: string[], value: boolean): Promise<void> {
  return apiPost<void>('/documents/bulk/favorite', { ids, value });
}

export function bulkMove(ids: string[], folderId: string | null): Promise<void> {
  return apiPost<void>('/documents/bulk/move', { ids, folder_id: folderId });
}

export function moveDocument(id: string, folderId: string | null): Promise<DocumentResponse> {
  return apiPost<DocumentResponse>(`/documents/${id}/move`, { folder_id: folderId });
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
