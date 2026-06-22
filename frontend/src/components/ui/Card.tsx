interface Props {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
  hover?: boolean;
  glow?: boolean;
}

export function Card({ children, className = '', padding = true, hover = false, glow = false }: Props) {
  return (
    <div
      className={[
        'rounded-2xl border border-white/[0.07] bg-white/[0.03] backdrop-blur-xl',
        'shadow-[0_4px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.05)]',
        padding ? 'p-6' : '',
        hover ? 'transition-all duration-300 hover:border-white/[0.12] hover:bg-white/[0.05] hover:shadow-[0_8px_40px_rgba(0,0,0,0.5),0_0_20px_rgba(99,102,241,0.08)] hover:-translate-y-0.5' : '',
        glow ? 'shadow-[0_4px_24px_rgba(0,0,0,0.4),0_0_40px_rgba(99,102,241,0.12),inset_0_1px_0_rgba(255,255,255,0.08)]' : '',
        className,
      ].filter(Boolean).join(' ')}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  icon,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
            {icon}
          </div>
        )}
        <div>
          <h2 className="text-sm font-semibold text-slate-100 tracking-tight">{title}</h2>
          {subtitle && (
            <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  icon,
  trend,
  color = 'indigo',
  href,
  loading = false,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  trend?: string;
  color?: 'indigo' | 'emerald' | 'amber' | 'rose' | 'blue' | 'violet' | 'sky' | 'pink' | 'slate';
  href?: string;
  loading?: boolean;
}) {
  const colorMap = {
    indigo: 'bg-indigo-500/10 text-indigo-400',
    emerald: 'bg-emerald-500/10 text-emerald-400',
    amber: 'bg-amber-500/10 text-amber-400',
    rose: 'bg-rose-500/10 text-rose-400',
    blue: 'bg-blue-500/10 text-blue-400',
    violet: 'bg-violet-500/10 text-violet-400',
    sky: 'bg-sky-500/10 text-sky-400',
    pink: 'bg-pink-500/10 text-pink-400',
    slate: 'bg-slate-500/10 text-slate-400',
  };

  const content = (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-widest">{label}</p>
        {loading ? (
          <div className="mt-2 h-8 w-16 rounded shimmer" />
        ) : (
          <p className="mt-1.5 text-3xl font-bold tracking-tight text-slate-100">{value}</p>
        )}
        {trend && !loading && (
          <p className="mt-1 text-xs text-slate-500">{trend}</p>
        )}
      </div>
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${colorMap[color]}`}>
        {icon}
      </div>
    </div>
  );

  return (
    <Card hover className="cursor-pointer">
      {content}
    </Card>
  );
}
