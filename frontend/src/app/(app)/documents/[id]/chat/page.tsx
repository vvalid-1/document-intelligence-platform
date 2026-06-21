'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  clearDocumentSession,
  getOrCreateDocumentSession,
  listMessages,
  sendMessage,
} from '@/lib/api/chat';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Input';

const GREETING_RE = /^\s*(hi|hello|hey|howdy|greetings|sup|yo|good\s+(morning|afternoon|evening))\W*\s*$/i;
const GREETING_REPLY = "Hello! I'm your document assistant. Ask me anything about this document.";

interface Message {
  role: 'user' | 'assistant';
  content: string;
  pending?: boolean;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [initError, setInitError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  async function initSession(forceNew = false) {
    setInitError('');
    try {
      if (forceNew) clearDocumentSession(id);
      const s = await getOrCreateDocumentSession(id);
      setSessionId(s.id);
      const history = await listMessages(s.id);
      setMessages(
        history
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })),
      );
    } catch {
      setInitError('Failed to start chat session');
    }
  }

  useEffect(() => {
    void initSession();
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || !sessionId || busy) return;
    const userMsg = input.trim();
    setInput('');
    setError('');
    setBusy(true);

    if (GREETING_RE.test(userMsg)) {
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: userMsg },
        { role: 'assistant', content: GREETING_REPLY },
      ]);
      setBusy(false);
      return;
    }

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMsg },
      { role: 'assistant', content: '', pending: true },
    ]);

    try {
      const r = await sendMessage(sessionId, userMsg);
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', content: r.answer };
        return copy;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to get response');
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  async function handleNewChat() {
    setMessages([]);
    setSessionId(null);
    setError('');
    await initSession(true);
  }

  return (
    <div className="flex h-full">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-gray-200 lg:flex lg:flex-col dark:border-slate-700">
        <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2 dark:bg-slate-800 dark:border-slate-700">
          <span className="text-xs font-medium text-gray-500 dark:text-slate-400">Document preview</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Chat panel */}
      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-3 dark:bg-slate-800 dark:border-slate-700">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="sm">←</Button>
          </Link>
          <h1 className="flex-1 text-sm font-semibold text-gray-900 dark:text-slate-100">Chat with document</h1>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => void handleNewChat()}
          >
            New chat
          </Button>
        </div>

        {initError && (
          <div className="border-b border-red-100 bg-red-50 px-6 py-2 text-sm text-red-600">
            {initError}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 && !initError && (
            <div className="mt-16 text-center text-sm text-gray-400 dark:text-slate-500">
              Ask anything about this document.
            </div>
          )}
          <div className="mx-auto max-w-2xl space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'border border-gray-200 bg-white text-gray-800 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100'
                  }`}
                >
                  {m.pending ? <span className="animate-pulse">▌</span> : m.content}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {error && (
          <div className="border-t border-red-100 bg-red-50 px-6 py-2 text-sm text-red-600">
            {error}
          </div>
        )}

        <div className="border-t border-gray-200 bg-white px-6 py-4 dark:bg-slate-800 dark:border-slate-700">
          <div className="mx-auto flex max-w-2xl gap-3">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about the document…"
              rows={2}
              className="flex-1 resize-none"
              disabled={busy || !sessionId}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
            />
            <Button
              onClick={() => void handleSend()}
              loading={busy}
              disabled={!input.trim() || !sessionId}
            >
              Send
            </Button>
          </div>
          <p className="mx-auto mt-1.5 max-w-2xl text-xs text-gray-400 dark:text-slate-500">
            Enter to send · Shift+Enter for new line · Response may take up to 3 minutes on CPU
          </p>
        </div>
      </div>
    </div>
  );
}
