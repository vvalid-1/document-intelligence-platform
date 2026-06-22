interface TimelineEvent {
  label: string;
  sublabel?: string;
  date: string;
  icon: string;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const ICON_COLORS: Record<string, string> = {
  '📤': 'bg-blue-500/10 text-blue-400',
  '⚙': 'bg-amber-500/10 text-amber-400',
  '✅': 'bg-emerald-500/10 text-emerald-400',
  '💬': 'bg-indigo-500/10 text-indigo-400',
  '🔍': 'bg-violet-500/10 text-violet-400',
  '✏': 'bg-sky-500/10 text-sky-400',
  '🌐': 'bg-green-500/10 text-green-400',
  '✍': 'bg-pink-500/10 text-pink-400',
  '🎙': 'bg-purple-500/10 text-purple-400',
  '❌': 'bg-rose-500/10 text-rose-400',
};

function iconBg(icon: string): string {
  return ICON_COLORS[icon] ?? 'bg-slate-500/10 text-slate-400';
}

export function ActivityTimeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) return null;

  const sorted = [...events].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
  );

  return (
    <div className="space-y-0">
      {sorted.map((ev, i) => (
        <div key={i} className="flex gap-3.5">
          <div className="flex flex-col items-center">
            <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-xl text-sm ${iconBg(ev.icon)}`}>
              {ev.icon}
            </div>
            {i < sorted.length - 1 && (
              <div className="my-1 w-px flex-1 bg-white/[0.05]" style={{ minHeight: 16 }} />
            )}
          </div>
          <div className="pb-4 pt-0.5">
            <p className="text-sm font-medium text-slate-200">{ev.label}</p>
            {ev.sublabel && (
              <p className="text-xs text-slate-500">{ev.sublabel}</p>
            )}
            <p className="mt-0.5 text-[11px] text-slate-700">{fmtDate(ev.date)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export type { TimelineEvent };
