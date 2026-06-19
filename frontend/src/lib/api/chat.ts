import type { ChatMessageResponse, ChatResponse, ChatSessionResponse } from '@/types/api';
import { apiGet, apiPost } from './client';

export function createSession(documentId?: string): Promise<ChatSessionResponse> {
  return apiPost<ChatSessionResponse>('/chat/sessions', {
    document_id: documentId ?? null,
    session_name: null,
  });
}

export function getSession(id: string): Promise<ChatSessionResponse> {
  return apiGet<ChatSessionResponse>(`/chat/sessions/${id}`);
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
