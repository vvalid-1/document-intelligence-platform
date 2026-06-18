import type { ReviewResponse } from '@/types/api';
import { apiPost } from './client';

export function reviewDocument(documentId: string): Promise<ReviewResponse> {
  return apiPost<ReviewResponse>(`/documents/${documentId}/review`);
}
