import { useCallback, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import type { RoleType } from "../api/types"

// The mode toggle scopes every view. Its value is exactly a RoleType, so no
// translation layer is needed between UI mode and API role_type filters.
export type Mode = RoleType

const MODE_STORAGE_KEY = "econpilot.mode"
const DEFAULT_MODE: Mode = "internship"

function isMode(value: string | null): value is Mode {
  return value === "internship" || value === "full_time"
}

function readStoredMode(): Mode {
  if (typeof window === "undefined") return DEFAULT_MODE
  const stored = window.localStorage.getItem(MODE_STORAGE_KEY)
  return isMode(stored) ? stored : DEFAULT_MODE
}

/** Mode persists in both the URL (?mode=) and localStorage, and drives every
 * scoped query. Reading the URL first means a shared/bookmarked link always
 * wins over whatever was last stored locally. */
export function useMode(): [Mode, (next: Mode) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlMode = searchParams.get("mode")
  const mode: Mode = isMode(urlMode) ? urlMode : readStoredMode()

  useEffect(() => {
    window.localStorage.setItem(MODE_STORAGE_KEY, mode)

    if (!isMode(urlMode)) {
      const next = new URLSearchParams(searchParams)
      next.set("mode", mode)
      setSearchParams(next, { replace: true })
    }
  }, [mode, urlMode])

  const setMode = useCallback(
    (next: Mode) => {
      window.localStorage.setItem(MODE_STORAGE_KEY, next)
      const params = new URLSearchParams(searchParams)
      params.set("mode", next)
      setSearchParams(params)
    },
    [searchParams],
  )

  return [mode, setMode]
}
