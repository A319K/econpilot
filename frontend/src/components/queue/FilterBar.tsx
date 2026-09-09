import type { RefObject } from "react"
import { JOB_FAMILIES, type JobFamily, type RoleType } from "../../api/types"

export interface QueueFilters {
  minScore: number
  family: JobFamily | "all"
  location: string
  targetsOnly: boolean
  entryLevelOnly: boolean
  sort: "score" | "recent"
  search: string
}

// The stored values are snake_case enum members; these are what an econ student
// would actually call them.
const FAMILY_LABELS: Record<JobFamily, string> = {
  finance: "finance",
  consulting: "consulting",
  data_analytics: "data & analytics",
  corporate: "corporate",
  policy_research: "policy & research",
  other: "other",
}

const selectClass =
  "border border-(--color-border) bg-(--color-bg) px-1 py-0.5 text-(--color-fg)"

export function FilterBar({
  filters,
  onChange,
  searchInputRef,
  mode,
}: {
  filters: QueueFilters
  onChange: (next: QueueFilters) => void
  searchInputRef: RefObject<HTMLInputElement | null>
  mode: RoleType
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-(--color-border) px-3 py-2 text-xs">
      <label className="flex items-center gap-2">
        <span className="text-(--color-fg-dim)">min score</span>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={filters.minScore}
          onChange={(e) => onChange({ ...filters, minScore: Number(e.target.value) })}
          className="accent-(--color-accent) w-24"
        />
        <span className="text-(--color-fg-bright) w-6 tabular-nums">{filters.minScore}</span>
      </label>

      <label className="flex items-center gap-1.5">
        <span className="text-(--color-fg-dim)">field</span>
        <select
          value={filters.family}
          onChange={(e) =>
            onChange({ ...filters, family: e.target.value as JobFamily | "all" })
          }
          className={selectClass}
        >
          <option value="all">all fields</option>
          {JOB_FAMILIES.map((family) => (
            <option key={family} value={family}>
              {FAMILY_LABELS[family]}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5">
        <span className="text-(--color-fg-dim)">location</span>
        <input
          type="text"
          placeholder="city, state, or remote"
          value={filters.location}
          onChange={(e) => onChange({ ...filters, location: e.target.value })}
          className="w-40 border border-(--color-border) bg-(--color-bg) px-1.5 py-0.5 text-(--color-fg) placeholder:text-(--color-fg-faint)"
        />
      </label>

      <label className="flex items-center gap-1.5">
        <span className="text-(--color-fg-dim)">sort</span>
        <select
          value={filters.sort}
          onChange={(e) => onChange({ ...filters, sort: e.target.value as "score" | "recent" })}
          className={selectClass}
        >
          <option value="score">top score</option>
          <option value="recent">most recent</option>
        </select>
      </label>

      <label className="flex items-center gap-1.5">
        <input
          type="checkbox"
          checked={filters.targetsOnly}
          onChange={(e) => onChange({ ...filters, targetsOnly: e.target.checked })}
          className="accent-(--color-accent)"
        />
        <span className="text-(--color-fg-dim)">targets only ★</span>
      </label>

      {mode === "full_time" && (
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={filters.entryLevelOnly}
            onChange={(e) => onChange({ ...filters, entryLevelOnly: e.target.checked })}
            className="accent-(--color-accent)"
          />
          <span className="text-(--color-fg-dim)">entry level only</span>
        </label>
      )}

      <label className="ml-auto flex items-center gap-1.5">
        <span className="text-(--color-fg-dim)">/</span>
        <input
          ref={searchInputRef}
          type="text"
          placeholder="search title or company…"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          className="w-56 border border-(--color-border) bg-(--color-bg) px-1.5 py-0.5 text-(--color-fg) placeholder:text-(--color-fg-faint)"
        />
      </label>
    </div>
  )
}
