type Color = 'green' | 'yellow' | 'red' | 'blue' | 'gray' | 'purple' | 'indigo' | 'orange';

interface Props {
  color?: Color;
  children: React.ReactNode;
  dot?: boolean;
}

const colorClass: Record<Color, string> = {
  green:  'bg-emerald-500/10 text-emerald-400 ring-1 ring-inset ring-emerald-500/20',
  yellow: 'bg-amber-500/10   text-amber-400   ring-1 ring-inset ring-amber-500/20',
  red:    'bg-rose-500/10    text-rose-400    ring-1 ring-inset ring-rose-500/20',
  blue:   'bg-blue-500/10    text-blue-400    ring-1 ring-inset ring-blue-500/20',
  gray:   'bg-slate-500/10   text-slate-400   ring-1 ring-inset ring-slate-500/20',
  purple: 'bg-purple-500/10  text-purple-400  ring-1 ring-inset ring-purple-500/20',
  indigo: 'bg-indigo-500/10  text-indigo-400  ring-1 ring-inset ring-indigo-500/20',
  orange: 'bg-orange-500/10  text-orange-400  ring-1 ring-inset ring-orange-500/20',
};

const dotClass: Record<Color, string> = {
  green: 'bg-emerald-400',
  yellow: 'bg-amber-400',
  red: 'bg-rose-400',
  blue: 'bg-blue-400',
  gray: 'bg-slate-400',
  purple: 'bg-purple-400',
  indigo: 'bg-indigo-400',
  orange: 'bg-orange-400',
};

export function Badge({ color = 'gray', children, dot = false }: Props) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium tracking-wide ${colorClass[color]}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotClass[color]}`} />}
      {children}
    </span>
  );
}

export function statusBadge(status: string) {
  const map: Record<string, { color: Color; label: string; dot?: boolean }> = {
    ready:      { color: 'green',  label: 'Ready',      dot: true },
    processing: { color: 'yellow', label: 'Processing', dot: true },
    uploaded:   { color: 'gray',   label: 'Uploaded',   dot: true },
    error:      { color: 'red',    label: 'Error',      dot: true },
  };
  const s = map[status] ?? { color: 'gray' as Color, label: status };
  return <Badge color={s.color} dot={s.dot}>{s.label}</Badge>;
}

export function severityBadge(severity: string) {
  const map: Record<string, Color> = { high: 'red', medium: 'yellow', low: 'blue' };
  return <Badge color={map[severity] ?? 'gray'}>{severity}</Badge>;
}
