import type { ApplicationStatus } from "../../api/types"
import { STATUS_COLOR_VAR, STATUS_LABELS } from "../../lib/status"

export function StatusTag({ status, className = "" }: { status: ApplicationStatus; className?: string }) {
  const color = STATUS_COLOR_VAR[status]
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium whitespace-nowrap ${className}`}
      style={{ color }}
    >
      <span aria-hidden="true">[</span>
      {STATUS_LABELS[status]}
      <span aria-hidden="true">]</span>
    </span>
  )
}
