import type { RefObject } from "react"
import { JOB_FAMILIES, JOB_SOURCES, type JobFamily, type JobSource, type RoleType } from "../../api/types"

export interface QueueFilters {
  minScore: number
  families: Set<JobFamily>
  source: JobSource | "all"
  targetsOnly: boolean
  entryLevelOnly: boolean
  sort: "score" | "recent"
  search: string
}

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
  function toggleFamily(family: JobFamily) {
    const next = new Set(filters.families)
    if (next.has(family)) next.delete(family)
    else next.add(family)
    onChange({ ...filters, families: next })
  }

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

      <div className="flex items-center gap-1">
        <span className="text-(--color-fg-dim) mr-1">family</span>
        {JOB_FAMILIES.map((family) => (
          <button
            key={family}
            onClick={() => toggleFamily(family)}
            className={`border px-1.5 py-0.5 ${
              filters.families.has(family)
                ? "border-(--color-accent) text-(--color-accent)"
                : "border-(--color-border) text-(--color-fg-dim) hover:text-(--color-fg-bright)"
            }`}
          >
            {family}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-1.5">
        <span className="text-(--color-fg-dim)">source</span>
        <select
          value={filters.source}
          onChange={(e) => onChange({ ...filters, source: e.target.value as JobSource | "all" })}
          className="border border-(--color-border) bg-(--color-bg) px-1 py-0.5 text-(--color-fg)"
        >
          <option value="all">all</option>
          {JOB_SOURCES.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5">
        <span className="text-(--color-fg-dim)">sort</span>
        <select
          value={filters.sort}
          onChange={(e) => onChange({ ...filters, sort: e.target.value as "score" | "recent" })}
          className="border border-(--color-border) bg-(--color-bg) px-1 py-0.5 text-(--color-fg)"
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
