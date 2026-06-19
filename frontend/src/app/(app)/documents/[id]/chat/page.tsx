'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { createSession, listMessages, sendMessage } from '@/lib/api/chat';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Input';

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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    createSession(id)
      .then(async (s) => {
        setSessionId(s.id);
        const history = await listMessages(s.id);
        setMessages(history.map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })));
      })
      .catch(() => setError('Failed to start chat session'));
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

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-3">
        <Link href={`/documents/${id}`}>
          <Button variant="ghost" size="sm">←</Button>
        </Link>
        <h1 className="text-sm font-semibold text-gray-900">Chat with document</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <div className="mt-16 text-center text-sm text-gray-400">
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
                    : 'border border-gray-200 bg-white text-gray-800'
                }`}
              >
                {m.pending ? (
                  <span className="animate-pulse">▌</span>
                ) : (
                  m.content
                )}
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

      <div className="border-t border-gray-200 bg-white px-6 py-4">
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
        <p className="mx-auto mt-1.5 max-w-2xl text-xs text-gray-400">
          Enter to send · Shift+Enter for new line · Response may take up to 3 minutes on CPU
        </p>
      </div>
    </div>
  );
}
