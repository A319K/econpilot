import type { StatusHistoryEntry } from "../../api/types"
import { formatTimestamp } from "../../lib/format"
import { STATUS_COLOR_VAR, STATUS_LABELS } from "../../lib/status"
import type { ApplicationStatus } from "../../api/types"

export function StatusTimeline({ history }: { history: StatusHistoryEntry[] | null }) {
  if (!history || history.length === 0) {
    return <p className="text-(--color-fg-dim) text-xs">no transitions recorded yet</p>
  }

  return (
    <ol className="flex flex-col gap-2 text-xs">
      {[...history].reverse().map((entry, i) => (
        <li key={i} className="border-l-2 border-(--color-border) pl-3">
          <div className="flex items-center gap-1.5">
            <span className="text-(--color-fg-faint) tabular-nums">{formatTimestamp(entry.timestamp)}</span>
            {entry.forced && (
              <span className="text-(--color-status-rejected) font-semibold">FORCED</span>
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5">
            <span className="text-(--color-fg-dim)">{entry.from}</span>
            <span className="text-(--color-fg-faint)">→</span>
            <span style={{ color: STATUS_COLOR_VAR[entry.to as ApplicationStatus] ?? undefined }}>
              {STATUS_LABELS[entry.to as ApplicationStatus] ?? entry.to}
            </span>
          </div>
          {entry.note && <p className="text-(--color-fg-dim) mt-0.5 italic">"{entry.note}"</p>}
        </li>
      ))}
    </ol>
  )
}
