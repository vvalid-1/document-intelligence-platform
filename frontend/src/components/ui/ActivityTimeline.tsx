interface TimelineEvent {
  label: string;
  sublabel?: string;
  date: string;
  icon: string;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleString();
}

export function ActivityTimeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) return null;

  const sorted = [...events].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  );

  return (
    <div>
      {sorted.map((ev, i) => (
        <div key={i} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm">
              {ev.icon}
            </div>
            {i < sorted.length - 1 && (
              <div className="mt-1 w-px flex-1 bg-gray-200" style={{ minHeight: 16 }} />
            )}
          </div>
          <div className="pb-4 pt-0.5">
            <p className="text-sm font-medium text-gray-900">{ev.label}</p>
            {ev.sublabel && (
              <p className="text-xs text-gray-500">{ev.sublabel}</p>
            )}
            <p className="mt-0.5 text-xs text-gray-400">{fmtDate(ev.date)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export type { TimelineEvent };
