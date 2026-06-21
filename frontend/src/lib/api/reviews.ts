import type { ReviewListResponse, ReviewResponse } from '@/types/api';
import { apiGet, apiPost } from './client';

export function reviewDocument(documentId: string): Promise<ReviewResponse> {
  return apiPost<ReviewResponse>(`/documents/${documentId}/review`);
}

export function listReviews(documentId: string): Promise<ReviewListResponse> {
  return apiGet<ReviewListResponse>(`/documents/${documentId}/reviews`);
}
