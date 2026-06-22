import { apiPost } from './client';
import type { SearchResponse } from '@/types/api';

export function searchDocuments(query: string, topK = 20, folderId?: string | null): Promise<SearchResponse> {
  return apiPost<SearchResponse>('/search', {
    query,
    top_k: topK,
    ...(folderId ? { folder_id: folderId } : {}),
  });
}
