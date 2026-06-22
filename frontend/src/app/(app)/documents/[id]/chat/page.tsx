'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { clearDocumentSession, getOrCreateDocumentSession, listMessages, sendMessage } from '@/lib/api/chat';
import { PdfPreview } from '@/components/ui/PdfPreview';
import { Button } from '@/components/ui/Button';

const GREETING_RE = /^\s*(hi|hello|hey|howdy|greetings|sup|yo|good\s+(morning|afternoon|evening))\W*\s*$/i;
const GREETING_REPLY = "Hello! I'm your document assistant. Ask me anything about this document.";

interface Message {
  role: 'user' | 'assistant';
  content: string;
  pending?: boolean;
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
          style={{ animationDelay: `${i * 150}ms`, animationDuration: '0.8s' }}
        />
      ))}
    </div>
  );
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  useEffect(() => { void initSession(); }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || !sessionId || busy) return;
    const userMsg = input.trim();
    setInput('');
    setError('');
    setBusy(true);
    textareaRef.current?.focus();

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
    setMessages([]); setSessionId(null); setError('');
    await initSession(true);
  }

  return (
    <div className="flex h-full bg-[#0a0f1e]">
      {/* PDF panel */}
      <div className="hidden w-5/12 shrink-0 border-r border-white/[0.06] lg:flex lg:flex-col">
        <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-4 py-3">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="xs">
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </Button>
          </Link>
          <span className="text-xs font-medium text-slate-600">Document preview</span>
          <div className="w-16" />
        </div>
        <div className="flex-1 overflow-hidden">
          <PdfPreview documentId={id} className="h-full" />
        </div>
      </div>

      {/* Chat panel */}
      <div className="flex flex-1 flex-col min-h-0">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-white/[0.06] bg-white/[0.02] px-6 py-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-indigo-500/10">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} className="text-indigo-400">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h1 className="flex-1 text-sm font-semibold text-slate-100">Chat with document</h1>
          <Link href={`/documents/${id}`} className="lg:hidden">
            <Button variant="ghost" size="xs">← Back</Button>
          </Link>
          <Button variant="glass" size="xs" disabled={busy} onClick={() => void handleNewChat()}>
            New chat
          </Button>
        </div>

        {initError && (
          <div className="border-b border-rose-500/20 bg-rose-500/[0.06] px-6 py-2.5 text-sm text-rose-400">
            {initError}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 scrollbar-thin">
          {messages.length === 0 && !initError && (
            <div className="flex flex-col items-center justify-center pt-16 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400">
                <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-sm font-medium text-slate-400">Ask anything about this document</p>
              <p className="mt-1 text-xs text-slate-600">The AI has read your document and can answer questions about it</p>
            </div>
          )}

          <div className="mx-auto max-w-2xl space-y-5">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 mt-1">
                    <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} className="text-indigo-400">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                )}
                <div
                  className={[
                    'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
                    m.role === 'user'
                      ? 'bg-gradient-to-r from-indigo-500 to-violet-600 text-white shadow-[0_4px_16px_rgba(99,102,241,0.3)]'
                      : 'border border-white/[0.08] bg-white/[0.04] text-slate-200',
                  ].join(' ')}
                >
                  {m.pending ? <TypingDots /> : m.content}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {error && (
          <div className="border-t border-rose-500/20 bg-rose-500/[0.06] px-6 py-2.5 text-sm text-rose-400">
            {error}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-white/[0.06] bg-white/[0.02] px-6 py-4">
          <div className="mx-auto flex max-w-2xl gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about the document…"
              rows={2}
              disabled={busy || !sessionId}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleSend(); }
              }}
              className={[
                'flex-1 resize-none rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm text-slate-100',
                'placeholder:text-slate-600 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/40',
                'transition-all duration-200 disabled:opacity-50 scrollbar-thin',
              ].join(' ')}
            />
            <Button
              onClick={() => void handleSend()}
              loading={busy}
              disabled={!input.trim() || !sessionId}
              size="md"
              className="self-end"
            >
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              Send
            </Button>
          </div>
          <p className="mx-auto mt-2 max-w-2xl text-[11px] text-slate-700">
            Enter to send · Shift+Enter for new line · Responses may take up to 3 minutes on CPU
          </p>
        </div>
      </div>
    </div>
  );
}
