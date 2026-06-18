import type { EditResponse } from '@/types/api';
import { apiPost } from './client';

export function editDocument(documentId: string, instruction: string): Promise<EditResponse> {
  return apiPost<EditResponse>(`/documents/${documentId}/edit`, { instruction });
}
