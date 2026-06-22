'use client';

import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'glass';
type Size = 'xs' | 'sm' | 'md' | 'lg';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClass: Record<Variant, string> = {
  primary: [
    'bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-semibold',
    'shadow-[0_4px_16px_rgba(99,102,241,0.4)]',
    'hover:shadow-[0_4px_24px_rgba(99,102,241,0.6)] hover:brightness-110',
    'active:scale-[0.98]',
    'disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed',
  ].join(' '),
  secondary: [
    'bg-white/[0.06] text-slate-200 border border-white/[0.1]',
    'hover:bg-white/[0.1] hover:border-white/[0.16]',
    'active:bg-white/[0.04] active:scale-[0.98]',
    'disabled:opacity-40 disabled:cursor-not-allowed',
  ].join(' '),
  danger: [
    'bg-gradient-to-r from-red-500 to-rose-600 text-white font-semibold',
    'shadow-[0_4px_16px_rgba(239,68,68,0.3)]',
    'hover:shadow-[0_4px_24px_rgba(239,68,68,0.5)] hover:brightness-110',
    'active:scale-[0.98]',
    'disabled:opacity-50 disabled:cursor-not-allowed',
  ].join(' '),
  ghost: [
    'bg-transparent text-slate-400',
    'hover:bg-white/[0.06] hover:text-slate-200',
    'active:bg-white/[0.04] active:scale-[0.98]',
  ].join(' '),
  glass: [
    'glass text-slate-200 border border-white/[0.1]',
    'hover:bg-white/[0.08] hover:border-white/[0.2]',
    'active:scale-[0.98]',
    'disabled:opacity-40 disabled:cursor-not-allowed',
  ].join(' '),
};

const sizeClass: Record<Size, string> = {
  xs: 'px-2.5 py-1 text-xs rounded-lg',
  sm: 'px-3.5 py-1.5 text-sm rounded-xl',
  md: 'px-4.5 py-2 text-sm rounded-xl',
  lg: 'px-6 py-2.5 text-sm rounded-xl',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={[
        'inline-flex items-center justify-center gap-2 font-medium',
        'transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/70 focus-visible:ring-offset-1 focus-visible:ring-offset-transparent',
        variantClass[variant],
        sizeClass[size],
        className,
      ].filter(Boolean).join(' ')}
    >
      {loading && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}
