import { useEffect, useState } from "react"
import { Outlet } from "react-router-dom"
import { HelpOverlay } from "../ui/HelpOverlay"
import { Rail } from "./Rail"

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable
}

export function Layout() {
  const [helpOpen, setHelpOpen] = useState(false)

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "?" && !isTypingTarget(e.target)) {
        e.preventDefault()
        setHelpOpen((open) => !open)
      } else if (e.key === "Escape") {
        setHelpOpen(false)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-(--color-bg) text-(--color-fg)">
      <div className="crt-texture" />
      <Rail onHelp={() => setHelpOpen(true)} />
      <main className="min-w-0 flex-1 overflow-y-auto">
        <Outlet context={{ openHelp: () => setHelpOpen(true) } satisfies LayoutContext} />
      </main>
      {helpOpen && <HelpOverlay onClose={() => setHelpOpen(false)} />}
    </div>
  )
}

export interface LayoutContext {
  openHelp: () => void
}
