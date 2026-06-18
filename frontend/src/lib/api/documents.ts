import type { DocumentListResponse, DocumentResponse } from '@/types/api';
import { apiDelete, apiGet, apiRequest } from './client';

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
