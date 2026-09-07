import type { ApplicationStatus } from "../../api/types"
import { KANBAN_STATUSES, STATUS_COLOR_VAR, STATUS_LABELS } from "../../lib/status"

export function StatusBars({ counts }: { counts: Record<ApplicationStatus, number> }) {
  const statuses: ApplicationStatus[] = [...KANBAN_STATUSES, "withdrawn"]
  const max = Math.max(1, ...statuses.map((s) => counts[s] ?? 0))

  return (
    <div className="flex flex-col gap-1.5">
      {statuses.map((status) => {
        const count = counts[status] ?? 0
        const widthPct = (count / max) * 100
        return (
          <div key={status} className="flex items-center gap-2 text-xs">
            <span className="text-(--color-fg-dim) w-24 shrink-0 text-right">{STATUS_LABELS[status]}</span>
            <div className="h-3 flex-1 bg-(--color-bg-inset)">
              <div
                className="h-full"
                style={{ width: `${widthPct}%`, backgroundColor: STATUS_COLOR_VAR[status] }}
              />
            </div>
            <span className="text-(--color-fg-bright) w-6 tabular-nums">{count}</span>
          </div>
        )
      })}
    </div>
  )
}
