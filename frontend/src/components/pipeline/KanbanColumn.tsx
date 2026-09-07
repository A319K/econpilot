import { useState } from "react"
import type { ApplicationListItem, ApplicationStatus } from "../../api/types"
import { STATUS_LABELS } from "../../lib/status"
import { Panel } from "../ui/Panel"
import { KanbanCard } from "./KanbanCard"

export function KanbanColumn({
  status,
  applications,
  selectedId,
  onOpen,
  onDropApplication,
}: {
  status: ApplicationStatus
  applications: ApplicationListItem[]
  selectedId: number | null
  onOpen: (id: number) => void
  onDropApplication: (applicationId: number, target: ApplicationStatus) => void
}) {
  const [isOver, setIsOver] = useState(false)

  return (
    <Panel
      title={`${STATUS_LABELS[status]} (${applications.length})`}
      className={`flex w-64 shrink-0 flex-col ${isOver ? "border-(--color-accent)" : ""}`}
      bodyClassName="flex flex-col gap-2 p-2 h-full overflow-y-auto"
    >
      <div
        data-testid={`kanban-column-${status}`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsOver(true)
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsOver(false)
          const id = Number(e.dataTransfer.getData("text/plain"))
          if (!Number.isNaN(id)) onDropApplication(id, status)
        }}
        className="flex min-h-24 flex-1 flex-col gap-2"
      >
        {applications.length === 0 && <p className="text-(--color-fg-faint) px-1 py-4 text-center">—</p>}
        {applications.map((application) => (
          <KanbanCard
            key={application.id}
            application={application}
            selected={application.id === selectedId}
            onOpen={() => onOpen(application.id)}
            onDragStart={(e) => {
              e.dataTransfer.setData("text/plain", String(application.id))
              e.dataTransfer.effectAllowed = "move"
            }}
          />
        ))}
      </div>
    </Panel>
  )
}
