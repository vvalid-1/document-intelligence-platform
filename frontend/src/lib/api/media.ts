import type { MediaAnalysisResponse } from '@/types/api';
import { apiGet, apiPost } from './client';

export function getMediaAnalysis(documentId: string): Promise<MediaAnalysisResponse> {
  return apiGet<MediaAnalysisResponse>(`/documents/${documentId}/media-analysis`);
}

export function retriggerMediaAnalysis(documentId: string): Promise<MediaAnalysisResponse> {
  return apiPost<MediaAnalysisResponse>(`/documents/${documentId}/media-analysis`);
}
