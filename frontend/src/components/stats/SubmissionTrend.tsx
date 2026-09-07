import type { DailyCount } from "../../api/types"

export function SubmissionTrend({ data }: { data: DailyCount[] }) {
  if (data.length === 0) {
    return <p className="text-(--color-fg-dim) text-xs">no submissions in the last 30 days</p>
  }

  const max = Math.max(1, ...data.map((d) => d.count))

  return (
    <div className="flex h-24 gap-1">
      {data.map((day) => (
        <div
          key={day.date}
          className="group flex h-full flex-1 flex-col justify-end"
          title={`${day.date}: ${day.count}`}
        >
          <div
            className="bg-(--color-accent) group-hover:bg-(--color-accent-dim) w-full transition-colors"
            style={{ height: `${Math.max(4, (day.count / max) * 100)}%` }}
          />
        </div>
      ))}
    </div>
  )
}
