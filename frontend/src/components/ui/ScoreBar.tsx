import { scoreTierColor } from "../../lib/status"

const BAR_LENGTH = 8

export function ScoreBar({ score, className = "" }: { score: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, score))
  const filled = Math.round((clamped / 100) * BAR_LENGTH)
  const bar = "█".repeat(filled) + "░".repeat(BAR_LENGTH - filled)
  const color = scoreTierColor(clamped)

  return (
    <span className={`inline-flex items-center gap-1.5 tabular-nums ${className}`}>
      <span aria-hidden="true" style={{ color, letterSpacing: "-1px" }}>
        {bar}
      </span>
      <span className="text-(--color-fg-bright) w-7 text-right">{Math.round(clamped)}</span>
    </span>
  )
}
