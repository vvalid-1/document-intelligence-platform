'use client';

import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = '', ...rest }: InputProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium text-gray-800 dark:text-slate-300">{label}</label>}
      <input
        {...rest}
        className={`rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400 dark:bg-slate-700 dark:text-slate-100 dark:placeholder:text-slate-400 dark:disabled:bg-slate-800 dark:disabled:text-slate-500 ${
          error
            ? 'border-red-400 focus:border-red-400 focus:ring-red-500/20 dark:border-red-600'
            : 'border-gray-300 hover:border-gray-400 focus:border-blue-500 focus:ring-blue-500/20 dark:border-slate-600 dark:hover:border-slate-500 dark:focus:border-blue-500'
        } ${className}`}
      />
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export function Textarea({ label, error, className = '', ...rest }: TextareaProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium text-gray-800 dark:text-slate-300">{label}</label>}
      <textarea
        {...rest}
        className={`rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 disabled:bg-gray-50 dark:bg-slate-700 dark:text-slate-100 dark:placeholder:text-slate-400 dark:disabled:bg-slate-800 ${
          error
            ? 'border-red-400 focus:border-red-400 focus:ring-red-500/20 dark:border-red-600'
            : 'border-gray-300 hover:border-gray-400 focus:border-blue-500 focus:ring-blue-500/20 dark:border-slate-600 dark:hover:border-slate-500 dark:focus:border-blue-500'
        } ${className}`}
      />
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
