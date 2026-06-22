'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { logout } from '@/lib/api/auth';
import { clearToken } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth';

const NAV_PRIMARY = [
  {
    href: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    href: '/documents',
    label: 'Documents',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    href: '/search',
    label: 'Search',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
  {
    href: '/documents/upload',
    label: 'Upload',
    accent: true,
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
      </svg>
    ),
  },
];

const NAV_LIBRARY = [
  {
    href: '/folders',
    label: 'Folders',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7a2 2 0 012-2h3.586a1 1 0 01.707.293L11 7h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
      </svg>
    ),
  },
  {
    href: '/favorites',
    label: 'Favorites',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
      </svg>
    ),
  },
  {
    href: '/archived',
    label: 'Archived',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
      </svg>
    ),
  },
  {
    href: '/trash',
    label: 'Trash',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    ),
  },
];

function NavLink({
  href,
  label,
  icon,
  active,
  accent = false,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
  accent?: boolean;
}) {
  return (
    <Link
      href={href}
      className={[
        'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
        'transition-all duration-200',
        active
          ? accent
            ? 'bg-gradient-to-r from-indigo-500/20 to-violet-500/10 text-indigo-300 border border-indigo-500/30'
            : 'bg-white/[0.08] text-white border border-white/[0.08]'
          : accent
          ? 'text-indigo-400 hover:bg-indigo-500/10 hover:text-indigo-300 border border-transparent hover:border-indigo-500/20'
          : 'text-slate-500 hover:bg-white/[0.05] hover:text-slate-200 border border-transparent',
      ].join(' ')}
    >
      <span className="shrink-0">{icon}</span>
      {label}
      {active && !accent && (
        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400" />
      )}
    </Link>
  );
}

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

  function isActive(href: string) {
    if (href === '/dashboard') return pathname === href;
    return pathname === href || pathname.startsWith(href + '/');
  }

  const initial = user?.full_name?.charAt(0).toUpperCase() ?? '?';

  return (
    <aside className="flex h-screen w-[220px] shrink-0 flex-col bg-[#080d1a] border-r border-white/[0.05]">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-[0_0_20px_rgba(99,102,241,0.4)]">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-bold leading-none text-white tracking-tight">DocIntel</p>
          <p className="mt-0.5 text-[10px] text-slate-600 tracking-wider uppercase">AI Platform</p>
        </div>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 scrollbar-thin">
        <div className="space-y-0.5">
          {NAV_PRIMARY.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={isActive(item.href)}
              accent={item.accent}
            />
          ))}
        </div>

        <div className="mt-6 mb-1.5 px-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-700">
            Library
          </p>
        </div>
        <div className="space-y-0.5">
          {NAV_LIBRARY.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={isActive(item.href)}
            />
          ))}
        </div>
      </nav>

      {/* User */}
      <div className="border-t border-white/[0.05] px-3 py-3">
        {user && (
          <div className="mb-2 flex items-center gap-2.5 rounded-xl px-2 py-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/30 to-violet-500/20 border border-indigo-500/20 text-[11px] font-bold text-indigo-300">
              {initial}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-slate-200">{user.full_name}</p>
              <p className="truncate text-[10px] text-slate-600">{user.email}</p>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-medium text-slate-600 transition-all duration-200 hover:bg-white/[0.04] hover:text-slate-400"
        >
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Sign out
        </button>
      </div>
    </aside>
  );
}
