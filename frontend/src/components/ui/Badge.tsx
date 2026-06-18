type Color = 'green' | 'yellow' | 'red' | 'blue' | 'gray' | 'purple';

interface Props {
  color?: Color;
  children: React.ReactNode;
}

const colorClass: Record<Color, string> = {
  green: 'bg-green-100 text-green-700',
  yellow: 'bg-yellow-100 text-yellow-700',
  red: 'bg-red-100 text-red-700',
  blue: 'bg-blue-100 text-blue-700',
  gray: 'bg-gray-100 text-gray-600',
  purple: 'bg-purple-100 text-purple-700',
};

export function Badge({ color = 'gray', children }: Props) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass[color]}`}>
      {children}
    </span>
  );
}

export function statusBadge(status: string) {
  const map: Record<string, { color: Color; label: string }> = {
    ready: { color: 'green', label: 'Ready' },
    processing: { color: 'yellow', label: 'Processing' },
    pending: { color: 'gray', label: 'Pending' },
    failed: { color: 'red', label: 'Failed' },
  };
  const s = map[status] ?? { color: 'gray' as Color, label: status };
  return <Badge color={s.color}>{s.label}</Badge>;
}

export function severityBadge(severity: string) {
  const map: Record<string, Color> = { high: 'red', medium: 'yellow', low: 'blue' };
  return <Badge color={map[severity] ?? 'gray'}>{severity}</Badge>;
}
