import type { FunnelStats } from "../../api/types"

const STAGES: { key: keyof Pick<FunnelStats, "submitted" | "oa" | "interview" | "offer">; label: string }[] = [
  { key: "submitted", label: "SUBMITTED" },
  { key: "oa", label: "OA" },
  { key: "interview", label: "INTERVIEW" },
  { key: "offer", label: "OFFER" },
]

const RATE_KEYS: (keyof FunnelStats["conversion_rates"])[] = [
  "submitted_to_oa",
  "oa_to_interview",
  "interview_to_offer",
]

export function FunnelPanel({ funnel }: { funnel: FunnelStats }) {
  const max = Math.max(1, funnel.submitted)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-end gap-4">
        {STAGES.map((stage, i) => (
          <div key={stage.key} className="flex flex-col items-center gap-1">
            <div className="flex h-20 w-10 items-end bg-(--color-bg-inset)">
              <div
                className="bg-(--color-accent) w-full"
                style={{ height: `${Math.max(2, (funnel[stage.key] / max) * 100)}%` }}
              />
            </div>
            <span className="text-(--color-fg-bright) text-xs tabular-nums">{funnel[stage.key]}</span>
            <span className="text-(--color-fg-dim) text-[10px]">{stage.label}</span>
            {i < STAGES.length - 1 && (
              <span className="text-(--color-fg-faint) text-[10px] tabular-nums">
                {(funnel.conversion_rates[RATE_KEYS[i]] * 100).toFixed(0)}% →
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
