export interface LogLine {
  timestamp: string
  text: string
  tone?: "default" | "error" | "success"
}

const TONE_COLOR: Record<NonNullable<LogLine["tone"]>, string> = {
  default: "var(--color-fg)",
  error: "var(--color-status-rejected)",
  success: "var(--color-accent)",
}

export function ProgressLog({ lines, className = "" }: { lines: LogLine[]; className?: string }) {
  return (
    <div className={`bg-(--color-bg-inset) p-2 font-mono text-xs leading-relaxed ${className}`}>
      {lines.length === 0 ? (
        <p className="text-(--color-fg-dim)">…</p>
      ) : (
        lines.map((line, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-(--color-fg-faint) shrink-0">{line.timestamp}</span>
            <span style={{ color: TONE_COLOR[line.tone ?? "default"] }}>{line.text}</span>
          </div>
        ))
      )}
    </div>
  )
}
