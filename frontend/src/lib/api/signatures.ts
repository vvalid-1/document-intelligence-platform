import type { SignatureListResponse, SignatureResponse, SignatureType } from '@/types/api';
import { apiGet, apiPost } from './client';

interface SignRequest {
  signature_type: SignatureType;
  typed_text: string | null;
  image_base64: string | null;
  x: number;
  y: number;
  page_number: number;
  field_name: string | null;
}

export function signDocument(documentId: string, body: SignRequest): Promise<SignatureResponse> {
  return apiPost<SignatureResponse>(`/documents/${documentId}/sign`, body);
}

export function listSignatures(documentId: string): Promise<SignatureListResponse> {
  return apiGet<SignatureListResponse>(`/documents/${documentId}/signatures`);
}
