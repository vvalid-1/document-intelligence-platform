'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { logout } from '@/lib/api/auth';
import { clearToken } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth';

const NAV = [
  { href: '/dashboard', label: 'Dashboard', icon: '⊞' },
  { href: '/documents', label: 'Documents', icon: '⎙' },
  { href: '/documents/upload', label: 'Upload', icon: '↑' },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // ignore errors on logout
    }
    clearAuth();
    clearToken();
    router.push('/login');
  }

  return (
    <aside className="flex h-screen w-56 flex-col bg-slate-900 text-slate-100">
      <div className="border-b border-slate-700 px-5 py-4">
        <span className="text-sm font-bold tracking-wide text-white">DocIntel</span>
        <p className="mt-0.5 text-[11px] text-slate-400">Intelligence Platform</p>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${active ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'}`}
            >
              <span className="text-base">{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-700 px-4 py-3">
        {user && (
          <div className="mb-2">
            <p className="truncate text-xs font-medium text-white">{user.full_name}</p>
            <p className="truncate text-[11px] text-slate-400">{user.email}</p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="w-full rounded-lg px-3 py-1.5 text-left text-xs text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
