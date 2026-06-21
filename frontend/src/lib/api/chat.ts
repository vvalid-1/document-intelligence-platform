import type { ChatMessageResponse, ChatResponse, ChatSessionResponse } from '@/types/api';
import { apiGet, apiPost } from './client';

const SESSION_STORAGE_KEY = (documentId: string) => `chat_session_${documentId}`;

export function createSession(documentId?: string): Promise<ChatSessionResponse> {
  return apiPost<ChatSessionResponse>('/chat/sessions', {
    document_id: documentId ?? null,
    session_name: null,
  });
}

export function getSession(id: string): Promise<ChatSessionResponse> {
  return apiGet<ChatSessionResponse>(`/chat/sessions/${id}`);
}

export async function getOrCreateDocumentSession(
  documentId: string,
): Promise<ChatSessionResponse> {
  const stored = typeof window !== 'undefined'
    ? localStorage.getItem(SESSION_STORAGE_KEY(documentId))
    : null;

  if (stored) {
    try {
      return await getSession(stored);
    } catch {
      localStorage.removeItem(SESSION_STORAGE_KEY(documentId));
    }
  }

  const session = await createSession(documentId);
  if (typeof window !== 'undefined') {
    localStorage.setItem(SESSION_STORAGE_KEY(documentId), session.id);
  }
  return session;
}

export function clearDocumentSession(documentId: string): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(SESSION_STORAGE_KEY(documentId));
  }
}

export async function listMessages(sessionId: string): Promise<ChatMessageResponse[]> {
  const session = await getSession(sessionId);
  return session.messages ?? [];
}

export function sendMessage(
  sessionId: string,
  question: string,
): Promise<ChatResponse> {
  return apiPost<ChatResponse>(`/chat/sessions/${sessionId}/messages`, { question });
}
