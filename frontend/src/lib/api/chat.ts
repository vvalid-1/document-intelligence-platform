import type { ChatMessageResponse, ChatSessionResponse } from '@/types/api';
import { apiGet, apiPost, postSseStream } from './client';

export function createSession(documentId?: string): Promise<ChatSessionResponse> {
  return apiPost<ChatSessionResponse>('/chat/sessions', {
    document_id: documentId ?? null,
    session_name: null,
  });
}

export function getSession(id: string): Promise<ChatSessionResponse> {
  return apiGet<ChatSessionResponse>(`/chat/sessions/${id}`);
}

export function listMessages(sessionId: string): Promise<ChatMessageResponse[]> {
  return apiGet<ChatMessageResponse[]>(`/chat/sessions/${sessionId}/messages`);
}

export function sendMessage(
  sessionId: string,
  content: string,
  onChunk: (token: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): Promise<() => void> {
  return postSseStream(
    `/chat/sessions/${sessionId}/messages`,
    { content },
    onChunk,
    onDone,
    onError,
  );
}
