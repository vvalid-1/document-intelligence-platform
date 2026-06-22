'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { login, getMe } from '@/lib/api/auth';
import { useAuthStore } from '@/lib/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

export default function LoginPage() {
  const router = useRouter();
  const { setAuth, token, hydrate, hydrated } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { hydrate(); }, [hydrate]);
  useEffect(() => { if (hydrated && token) router.push('/dashboard'); }, [hydrated, token, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await login(email, password);
      localStorage.setItem('auth_token', res.access_token);
      const user = await getMe();
      setAuth(res.access_token, { id: user.id, email: user.email, full_name: user.full_name, role: user.role });
      router.push('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0f1e] p-4">
      {/* Background mesh */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/4 top-1/4 h-80 w-80 rounded-full bg-indigo-600/10 blur-3xl" />
        <div className="absolute right-1/4 bottom-1/3 h-64 w-64 rounded-full bg-violet-600/8 blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm animate-fade-in">
        {/* Brand */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-[0_0_40px_rgba(99,102,241,0.5)]">
            <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">DocIntel</h1>
          <p className="mt-1.5 text-sm text-slate-500">Sign in to your workspace</p>
        </div>

        {/* Form card */}
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.04] p-8 shadow-[0_20px_60px_rgba(0,0,0,0.5)] backdrop-blur-xl">
          <form onSubmit={handleSubmit} className="space-y-5">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
              icon={
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              }
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
              icon={
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              }
            />

            {error && (
              <div className="flex items-center gap-2.5 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3">
                <svg width="16" height="16" className="shrink-0 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm text-rose-400">{error}</p>
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" loading={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-slate-700">
          Document Intelligence Platform — local AI, no cloud data
        </p>
      </div>
    </div>
  );
}
