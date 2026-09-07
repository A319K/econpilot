import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ApiError } from "../api/client"
import type { ApplicationStatus } from "../api/types"
import { KanbanColumn } from "../components/pipeline/KanbanColumn"
import { EmptyState } from "../components/ui/EmptyState"
import { useToast } from "../components/ui/Toast"
import { useApplications, useUpdateApplicationStatus } from "../hooks/useApplications"
import { useListKeyboardNav } from "../hooks/useListKeyboardNav"
import { useMode } from "../lib/mode"
import { KANBAN_STATUSES } from "../lib/status"

export function PipelinePage() {
  const [mode] = useMode()
  const navigate = useNavigate()
  const { push } = useToast()
  const [showWithdrawn, setShowWithdrawn] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const applicationsQuery = useApplications({ role_type: mode, page_size: 200 })
  const updateStatus = useUpdateApplicationStatus()

  const columns = showWithdrawn ? [...KANBAN_STATUSES, "withdrawn" as ApplicationStatus] : KANBAN_STATUSES

  const byStatus = useMemo(() => {
    const map = new Map<ApplicationStatus, typeof applicationsQuery.data>()
    for (const status of columns) map.set(status, [])
    for (const app of applicationsQuery.data ?? []) {
      if (!map.has(app.status)) continue
      map.get(app.status)!.push(app)
    }
    return map
  }, [applicationsQuery.data, columns])

  function attemptTransition(applicationId: number, target: ApplicationStatus, force = false) {
    updateStatus.mutate(
      { id: applicationId, payload: { status: target, force } },
      {
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            push({
              tone: "error",
              message: `Can't move to ${target}: ${error.detail}`,
              action: {
                label: "Force move anyway",
                onClick: () => attemptTransition(applicationId, target, true),
              },
            })
          } else {
            push({ tone: "error", message: `Move failed: ${error.message}` })
          }
        },
      },
    )
  }

  function handleDrop(applicationId: number, target: ApplicationStatus) {
    const application = (applicationsQuery.data ?? []).find((a) => a.id === applicationId)
    if (!application || application.status === target) return
    attemptTransition(applicationId, target)
  }

  const isEmpty = (applicationsQuery.data ?? []).length === 0

  // Flattened in column order so j/k moves through the board left-to-right,
  // top-to-bottom within each column.
  const orderedApplications = columns.flatMap((status) => byStatus.get(status) ?? [])

  useListKeyboardNav({
    items: orderedApplications,
    selectedId,
    onSelect: setSelectedId,
    onOpen: (application) => navigate(`/applications/${application.id}?mode=${mode}`),
  })

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-(--color-border) px-4 py-3">
        <h1 className="text-(--color-fg-bright) text-sm font-bold tracking-wide">PIPELINE</h1>
        <label className="text-(--color-fg-dim) flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={showWithdrawn}
            onChange={(e) => setShowWithdrawn(e.target.checked)}
            className="accent-(--color-accent)"
          />
          show withdrawn
        </label>
      </header>

      {applicationsQuery.isLoading ? (
        <p className="text-(--color-fg-dim) p-4 text-xs">loading…</p>
      ) : isEmpty ? (
        <EmptyState
          title="No applications yet"
          hint='Queue a job from the Queue view (press "q" on a row, or click Queue) to see it show up here.'
        />
      ) : (
        <div className="no-scrollbar flex flex-1 gap-3 overflow-x-auto p-3">
          {columns.map((status) => (
            <KanbanColumn
              key={status}
              status={status}
              applications={byStatus.get(status) ?? []}
              selectedId={selectedId}
              onOpen={(id) => {
                setSelectedId(id)
                navigate(`/applications/${id}?mode=${mode}`)
              }}
              onDropApplication={handleDrop}
            />
          ))}
        </div>
      )}
    </div>
  )
}
