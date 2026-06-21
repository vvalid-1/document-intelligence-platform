interface Props {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}

export function Card({ children, className = '', padding = true }: Props) {
  return (
    <div className={`rounded-2xl border border-gray-100 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700 ${padding ? 'p-6' : ''} ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-gray-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
