import type { Mode } from "../../lib/mode"

export function ModeToggle({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <div
      role="radiogroup"
      aria-label="Mode: internships or full-time"
      className="border border-(--color-accent) grid grid-cols-2"
    >
      <button
        type="button"
        role="radio"
        aria-checked={mode === "internship"}
        onClick={() => onChange("internship")}
        className={`px-2 py-2 text-xs font-bold tracking-widest transition-colors ${
          mode === "internship"
            ? "bg-(--color-accent) text-(--color-bg)"
            : "text-(--color-fg-dim) hover:text-(--color-fg-bright)"
        }`}
      >
        INTERN
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={mode === "full_time"}
        onClick={() => onChange("full_time")}
        className={`px-2 py-2 text-xs font-bold tracking-widest transition-colors border-l border-(--color-accent) ${
          mode === "full_time"
            ? "bg-(--color-accent) text-(--color-bg)"
            : "text-(--color-fg-dim) hover:text-(--color-fg-bright)"
        }`}
      >
        FULL-TIME
      </button>
    </div>
  )
}
