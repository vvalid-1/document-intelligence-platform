type Color = 'green' | 'yellow' | 'red' | 'blue' | 'gray' | 'purple';

interface Props {
  color?: Color;
  children: React.ReactNode;
}

const colorClass: Record<Color, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-900/40 dark:text-emerald-400 dark:ring-emerald-500/30',
  yellow: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-900/40 dark:text-amber-400 dark:ring-amber-500/30',
  red: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-900/40 dark:text-red-400 dark:ring-red-500/30',
  blue: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-900/40 dark:text-blue-400 dark:ring-blue-500/30',
  gray: 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/20 dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-500/30',
  purple: 'bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-600/20 dark:bg-purple-900/40 dark:text-purple-400 dark:ring-purple-500/30',
};

export function Badge({ color = 'gray', children }: Props) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colorClass[color]}`}>
      {children}
    </span>
  );
}

export function statusBadge(status: string) {
  const map: Record<string, { color: Color; label: string }> = {
    ready: { color: 'green', label: 'Ready' },
    processing: { color: 'yellow', label: 'Processing' },
    uploaded: { color: 'gray', label: 'Uploaded' },
    error: { color: 'red', label: 'Error' },
  };
  const s = map[status] ?? { color: 'gray' as Color, label: status };
  return <Badge color={s.color}>{s.label}</Badge>;
}

export function severityBadge(severity: string) {
  const map: Record<string, Color> = { high: 'red', medium: 'yellow', low: 'blue' };
  return <Badge color={map[severity] ?? 'gray'}>{severity}</Badge>;
}
