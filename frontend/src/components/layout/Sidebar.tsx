'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { logout } from '@/lib/api/auth';
import { clearToken } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

const NAV = [
  { href: '/dashboard', label: 'Dashboard', icon: '⊞' },
  { href: '/documents', label: 'Documents', icon: '⎙' },
  { href: '/search', label: 'Search', icon: '⌕' },
  { href: '/folders', label: 'Folders', icon: '📁' },
  { href: '/archived', label: 'Archived', icon: '📦' },
  { href: '/favorites', label: 'Favorites', icon: '★' },
  { href: '/trash', label: 'Trash', icon: '🗑' },
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

  const initial = user?.full_name?.charAt(0).toUpperCase() ?? '?';

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-slate-900">
      {/* Brand */}
      <div className="flex items-center gap-3 border-b border-slate-800 px-5 py-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600 shadow-sm">
          <span className="text-xs font-bold text-white">DI</span>
        </div>
        <div>
          <p className="text-sm font-semibold leading-none text-white">DocIntel</p>
          <p className="mt-1 text-[11px] text-slate-500">Intelligence Platform</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                active
                  ? 'bg-blue-600 font-medium text-white shadow-sm'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <span className="text-base">{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-slate-800 px-4 py-4">
        {user && (
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-semibold text-slate-300">
              {initial}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-white">{user.full_name}</p>
              <p className="truncate text-[11px] text-slate-500">{user.email}</p>
            </div>
          </div>
        )}
        <ThemeToggle />
        <button
          onClick={handleLogout}
          className="w-full rounded-lg px-3 py-2 text-left text-xs text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-300"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
