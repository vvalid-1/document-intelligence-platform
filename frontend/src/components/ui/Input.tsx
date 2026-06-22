'use client';

import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: React.ReactNode;
}

export function Input({ label, error, hint, icon, className = '', ...rest }: InputProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="mb-1.5 block text-xs font-medium text-slate-400 uppercase tracking-wider">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500">
            {icon}
          </div>
        )}
        <input
          {...rest}
          className={[
            'w-full rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm text-slate-100',
            'placeholder:text-slate-600',
            'focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/40',
            'transition-all duration-200',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            error ? 'border-rose-500/50 focus:border-rose-500/50 focus:ring-rose-500/40' : '',
            icon ? 'pl-10' : '',
            className,
          ].filter(Boolean).join(' ')}
        />
      </div>
      {error && <p className="mt-1.5 text-xs text-rose-400">{error}</p>}
      {hint && !error && <p className="mt-1.5 text-xs text-slate-600">{hint}</p>}
    </div>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Textarea({ label, error, hint, className = '', ...rest }: TextareaProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="mb-1.5 block text-xs font-medium text-slate-400 uppercase tracking-wider">
          {label}
        </label>
      )}
      <textarea
        {...rest}
        className={[
          'w-full rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-sm text-slate-100',
          'placeholder:text-slate-600',
          'focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/40',
          'transition-all duration-200 resize-none',
          error ? 'border-rose-500/50' : '',
          className,
        ].filter(Boolean).join(' ')}
      />
      {error && <p className="mt-1.5 text-xs text-rose-400">{error}</p>}
      {hint && !error && <p className="mt-1.5 text-xs text-slate-600">{hint}</p>}
    </div>
  );
}
