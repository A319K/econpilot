import { useState } from "react"
import { ALLOWED_TRANSITIONS, type ApplicationStatus } from "../../api/types"
import { STATUS_LABELS } from "../../lib/status"
import { Button } from "../ui/Button"

export function StatusTransitionPanel({
  currentStatus,
  note,
  onNoteChange,
  onTransition,
  pending,
}: {
  currentStatus: ApplicationStatus
  note: string
  onNoteChange: (note: string) => void
  onTransition: (target: ApplicationStatus, force?: boolean) => void
  pending: boolean
}) {
  const [showForce, setShowForce] = useState(false)
  const options = ALLOWED_TRANSITIONS[currentStatus]

  return (
    <div className="flex flex-col gap-2">
      <input
        type="text"
        value={note}
        onChange={(e) => onNoteChange(e.target.value)}
        placeholder="note for this transition (optional)…"
        className="border border-(--color-border) bg-(--color-bg-inset) text-(--color-fg) placeholder:text-(--color-fg-faint) w-full p-1.5 text-xs"
      />

      {options.length === 0 ? (
        <p className="text-(--color-fg-dim) text-xs">terminal status - no further transitions</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {options.map((target, i) => (
            <Button key={target} variant="primary" disabled={pending} onClick={() => onTransition(target)}>
              <span className="text-(--color-fg-dim) mr-1">{i + 1}</span>
              {STATUS_LABELS[target]}
            </Button>
          ))}
        </div>
      )}

      <button
        onClick={() => setShowForce((v) => !v)}
        className="text-(--color-fg-faint) hover:text-(--color-fg-dim) self-start text-[10px]"
      >
        {showForce ? "hide" : "show"} force transition (bypasses validation)
      </button>

      {showForce && (
        <div className="border border-(--color-status-rejected) flex flex-wrap gap-1.5 p-2">
          {(Object.keys(STATUS_LABELS) as ApplicationStatus[])
            .filter((s) => s !== currentStatus)
            .map((target) => (
              <Button key={target} variant="danger" disabled={pending} onClick={() => onTransition(target, true)}>
                force → {STATUS_LABELS[target]}
              </Button>
            ))}
        </div>
      )}
    </div>
  )
}
