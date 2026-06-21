import type { TranslationLanguage, TranslationResponse } from '@/types/api';
import { apiPost } from './client';

export function translateDocument(
  documentId: string,
  targetLanguage: TranslationLanguage,
): Promise<TranslationResponse> {
  return apiPost<TranslationResponse>(`/documents/${documentId}/translate`, {
    target_language: targetLanguage,
  });
}
