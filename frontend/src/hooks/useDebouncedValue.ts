import { useEffect, useState } from "react"

/**
 * Returns `value` after it has stopped changing for `delayMs`.
 *
 * Used for filters that hit the API on every keystroke: the queue's location
 * filter runs server-side (client-side filtering would only ever see the rows
 * already fetched), so it needs to wait for a pause in typing.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
