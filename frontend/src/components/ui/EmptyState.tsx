import type { ReactNode } from "react"

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <p className="text-(--color-fg-dim)" aria-hidden="true">
        ░░░░░░░░
      </p>
      <p className="text-(--color-fg-bright) text-sm font-medium">{title}</p>
      {hint && <p className="text-(--color-fg-dim) max-w-sm text-xs leading-relaxed">{hint}</p>}
      {action}
    </div>
  )
}
