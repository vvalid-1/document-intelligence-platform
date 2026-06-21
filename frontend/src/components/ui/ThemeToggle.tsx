'use client';

import { useEffect, useState } from 'react';
import { getTheme, setTheme } from '@/lib/theme';
import type { Theme } from '@/lib/theme';

export function ThemeToggle() {
  const [theme, setLocal] = useState<Theme>('light');

  useEffect(() => {
    setLocal(getTheme());
  }, []);

  function toggle() {
    const next: Theme = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    setLocal(next);
  }

  return (
    <button
      onClick={toggle}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      className="w-full rounded-lg px-3 py-2 text-left text-xs text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-300"
    >
      <span className="mr-1.5">{theme === 'dark' ? '☀' : '☾'}</span>
      {theme === 'dark' ? 'Light mode' : 'Dark mode'}
    </button>
  );
}
