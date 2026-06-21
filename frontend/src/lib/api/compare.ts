import { apiGet, getToken } from './client';

export interface DocumentTextResponse {
  text: string;
  chunk_count: number;
}

export function getDocumentText(documentId: string): Promise<DocumentTextResponse> {
  return apiGet<DocumentTextResponse>(`/documents/${documentId}/text`);
}

export async function getVersionText(documentId: string, versionId: string): Promise<string> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(
    `/api/v1/documents/${documentId}/versions/${versionId}/download?fmt=txt`,
    { headers },
  );

  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(body.detail ?? `Failed to load version text (HTTP ${res.status})`);
  }

  return res.text();
}
