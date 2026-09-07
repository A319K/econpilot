import type { ReactNode } from "react"

interface PanelProps {
  title?: string
  titleExtra?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  accent?: boolean
}

/** A TUI-style bordered panel with the title embedded in the top border
 * line, e.g. "─┤ QUEUE ├─", rendered as styled text (not an image). */
export function Panel({ title, titleExtra, children, className = "", bodyClassName = "", accent = false }: PanelProps) {
  return (
    <div
      className={`relative border ${accent ? "border-(--color-accent)" : "border-(--color-border)"} bg-(--color-bg-panel) ${className}`}
    >
      {title && (
        <div className="absolute -top-[0.65em] left-3 flex items-baseline gap-1 bg-(--color-bg-panel) px-1.5">
          <span className="text-(--color-fg-dim) text-xs">┤</span>
          <span className="text-xs font-semibold tracking-wider text-(--color-fg-bright) uppercase">
            {title}
          </span>
          {titleExtra}
          <span className="text-(--color-fg-dim) text-xs">├</span>
        </div>
      )}
      <div className={bodyClassName || "p-3"}>{children}</div>
    </div>
  )
}
