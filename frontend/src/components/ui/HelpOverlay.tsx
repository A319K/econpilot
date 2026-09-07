const SHORTCUTS: [string, string][] = [
  ["j / k", "move selection down / up"],
  ["enter", "open selected row"],
  ["q", "queue selected job"],
  ["1-9", "jump to status transition N (detail view)"],
  ["/", "focus search"],
  ["?", "toggle this help"],
  ["esc", "close overlay / clear search"],
]

export function HelpOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div
        className="relative w-full max-w-md border border-(--color-accent) bg-(--color-bg-panel) p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute -top-[0.65em] left-3 bg-(--color-bg-panel) px-1.5 text-xs font-semibold tracking-wider text-(--color-accent) uppercase">
          ┤ keyboard shortcuts ├
        </div>
        <dl className="mt-2 flex flex-col gap-1.5 text-xs">
          {SHORTCUTS.map(([key, desc]) => (
            <div key={key} className="flex justify-between gap-4">
              <dt className="text-(--color-accent) shrink-0 font-semibold">{key}</dt>
              <dd className="text-(--color-fg-dim) text-right">{desc}</dd>
            </div>
          ))}
        </dl>
        <p className="text-(--color-fg-faint) mt-3 text-right text-[10px]">press esc or click to close</p>
      </div>
    </div>
  )
}
