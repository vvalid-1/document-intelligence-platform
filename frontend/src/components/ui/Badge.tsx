type Color = 'green' | 'yellow' | 'red' | 'blue' | 'gray' | 'purple';

interface Props {
  color?: Color;
  children: React.ReactNode;
}

const colorClass: Record<Color, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20',
  yellow: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20',
  red: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20',
  blue: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20',
  gray: 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/20',
  purple: 'bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-600/20',
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
