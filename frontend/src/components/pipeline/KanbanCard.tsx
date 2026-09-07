import type { ApplicationListItem } from "../../api/types"
import { formatDaysInStage } from "../../lib/format"

export function KanbanCard({
  application,
  onOpen,
  onDragStart,
  selected,
}: {
  application: ApplicationListItem
  onOpen: () => void
  onDragStart: (e: React.DragEvent) => void
  selected: boolean
}) {
  // status_history isn't included in list rows, so updated_at (bumped on
  // every transition) is used as a "time since last activity" proxy.
  const days = formatDaysInStage(application.updated_at)

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onOpen}
      data-testid={`kanban-card-${application.id}`}
      className={`cursor-grab border bg-(--color-bg-raised) p-2 text-xs active:cursor-grabbing ${
        selected ? "border-(--color-accent)" : "border-(--color-border)"
      }`}
    >
      <p className="text-(--color-fg-bright) truncate font-medium" title={application.job.title}>
        {application.job.title}
      </p>
      <p className="text-(--color-fg-dim) truncate">{application.job.company_name}</p>
      <div className="mt-1.5 flex items-center justify-between">
        <span className="text-(--color-fg-faint) tabular-nums">{days}d in stage</span>
        <span className="flex items-center gap-1">
          <span
            title={application.resume_version_id ? "resume attached" : "no resume"}
            className={application.resume_version_id ? "text-(--color-accent)" : "text-(--color-fg-faint)"}
          >
            R
          </span>
          <span
            title={application.cover_letter_id ? "cover letter attached" : "no cover letter"}
            className={application.cover_letter_id ? "text-(--color-accent)" : "text-(--color-fg-faint)"}
          >
            C
          </span>
        </span>
      </div>
    </div>
  )
}
