import { useEffect, useState } from "react"

const FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

export function Spinner({ label, className = "" }: { label?: string; className?: string }) {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setFrame((f) => (f + 1) % FRAMES.length), 80)
    return () => clearInterval(id)
  }, [])

  return (
    <span className={`inline-flex items-center gap-1.5 text-(--color-accent) ${className}`} role="status">
      <span aria-hidden="true">{FRAMES[frame]}</span>
      {label && <span className="text-(--color-fg-dim)">{label}</span>}
    </span>
  )
}
