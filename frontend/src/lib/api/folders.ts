import type { FolderListResponse, FolderResponse } from '@/types/api';
import { apiDelete, apiGet, apiPatch, apiPost } from './client';

export function listFolders(): Promise<FolderListResponse> {
  return apiGet<FolderListResponse>('/folders');
}

export function createFolder(name: string): Promise<FolderResponse> {
  return apiPost<FolderResponse>('/folders', { name });
}

export function renameFolder(id: string, name: string): Promise<FolderResponse> {
  return apiPatch<FolderResponse>(`/folders/${id}`, { name });
}

export function deleteFolder(id: string): Promise<void> {
  return apiDelete<void>(`/folders/${id}`);
}

export function listFolderDocuments(folderId: string, page = 1, pageSize = 20) {
  return apiGet<import('@/types/api').DocumentListResponse>(
    `/folders/${folderId}/documents?page=${page}&page_size=${pageSize}`
  );
}
