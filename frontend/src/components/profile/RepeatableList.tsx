import type { ReactNode } from "react"
import { Button } from "../ui/Button"

interface RepeatableListProps<T> {
  items: T[]
  onChange: (items: T[]) => void
  makeEmpty: () => T
  /** Heading for one entry, e.g. "Barclays — Summer Analyst". */
  titleOf: (item: T, index: number) => string
  addLabel: string
  emptyLabel: string
  children: (item: T, update: (patch: Partial<T>) => void, index: number) => ReactNode
}

/**
 * Add/remove wrapper for the list-shaped parts of the profile (education,
 * jobs, projects). Keeps every section behaving identically so there's one
 * interaction to learn, not three.
 */
export function RepeatableList<T>({
  items,
  onChange,
  makeEmpty,
  titleOf,
  addLabel,
  emptyLabel,
  children,
}: RepeatableListProps<T>) {
  const update = (index: number, patch: Partial<T>) => {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index))

  return (
    <div className="flex flex-col gap-3">
      {items.length === 0 ? (
        <p className="text-(--color-fg-faint) text-xs">{emptyLabel}</p>
      ) : null}

      {items.map((item, index) => (
        <div
          key={index}
          className="flex flex-col gap-2 border border-(--color-border) p-2"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-(--color-fg-bright) text-xs font-bold">
              {titleOf(item, index) || `entry ${index + 1}`}
            </span>
            <Button variant="danger" onClick={() => remove(index)} aria-label="remove entry">
              remove
            </Button>
          </div>
          {children(item, (patch) => update(index, patch), index)}
        </div>
      ))}

      <div>
        <Button onClick={() => onChange([...items, makeEmpty()])}>{addLabel}</Button>
      </div>
    </div>
  )
}
