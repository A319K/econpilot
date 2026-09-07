import { useEffect } from "react"

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable
}

interface ListKeyboardNavOptions<T extends { id: number }> {
  items: T[]
  selectedId: number | null
  onSelect: (id: number) => void
  onOpen?: (item: T) => void
  onQueue?: (item: T) => void
  searchInputRef?: React.RefObject<HTMLInputElement | null>
  enabled?: boolean
}

/** j/k row navigation, Enter to open, q to queue, / to focus search - the
 * shared keyboard grammar for /queue and /pipeline list-shaped views. */
export function useListKeyboardNav<T extends { id: number }>({
  items,
  selectedId,
  onSelect,
  onOpen,
  onQueue,
  searchInputRef,
  enabled = true,
}: ListKeyboardNavOptions<T>) {
  useEffect(() => {
    if (!enabled) return

    function handler(e: KeyboardEvent) {
      const typing = isTypingTarget(e.target)

      if (e.key === "/" && !typing) {
        e.preventDefault()
        searchInputRef?.current?.focus()
        return
      }
      if (e.key === "Escape" && typing) {
        ;(e.target as HTMLElement).blur()
        return
      }
      if (typing || items.length === 0) return

      const currentIndex = items.findIndex((item) => item.id === selectedId)

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault()
        const next = items[Math.min(items.length - 1, currentIndex + 1)] ?? items[0]
        onSelect(next.id)
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault()
        const prev = items[Math.max(0, currentIndex - 1)] ?? items[0]
        onSelect(prev.id)
      } else if (e.key === "Enter") {
        const item = items[currentIndex]
        if (item) onOpen?.(item)
      } else if (e.key === "q") {
        const item = items[currentIndex]
        if (item) onQueue?.(item)
      }
    }

    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [items, selectedId, onSelect, onOpen, onQueue, searchInputRef, enabled])
}
