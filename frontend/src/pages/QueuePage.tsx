import { useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import type { Job } from "../api/types"
import { FilterBar, type QueueFilters } from "../components/queue/FilterBar"
import { ExternalSearchLinks } from "../components/queue/ExternalSearchLinks"
import { PrepareLogPanel } from "../components/queue/PrepareLogPanel"
import { QueueTable } from "../components/queue/QueueTable"
import { ScanPanel } from "../components/queue/ScanPanel"
import { EmptyState } from "../components/ui/EmptyState"
import { Panel } from "../components/ui/Panel"
import { SkeletonRows } from "../components/ui/SkeletonRows"
import { useToast } from "../components/ui/Toast"
import { useApplications, useQueueJob } from "../hooks/useApplications"
import { useCompanyMap } from "../hooks/useCompanyMap"
import { usePrepareJob } from "../hooks/useJobs"
import { useJobs } from "../hooks/useJobs"
import { useDebouncedValue } from "../hooks/useDebouncedValue"
import { useListKeyboardNav } from "../hooks/useListKeyboardNav"
import { ApiError } from "../api/client"
import { useMode } from "../lib/mode"

const DEFAULT_FILTERS: QueueFilters = {
  minScore: 0,
  family: "all",
  location: "",
  targetsOnly: false,
  entryLevelOnly: true,
  sort: "score",
  search: "",
}

// Titles containing any of these (whole word, case-insensitive) are above
// entry level. Short tokens rely on word boundaries so e.g. "sr" doesn't hit
// "SRE" and "vp" doesn't hit arbitrary substrings.
const SENIOR_TITLE_RE =
  /\b(senior|sr|staff|principal|lead|distinguished|architect|director|manager|mgr|head|chief|vp|svp|evp)\b/i

export function QueuePage() {
  const [mode] = useMode()
  const navigate = useNavigate()
  const { push } = useToast()
  const companyMap = useCompanyMap()
  const searchInputRef = useRef<HTMLInputElement>(null)

  const [filters, setFilters] = useState<QueueFilters>(DEFAULT_FILTERS)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [preparingJob, setPreparingJob] = useState<Job | null>(null)

  // Entry-level filtering only applies to full-time roles.
  const entryLevelActive = mode === "full_time" && filters.entryLevelOnly
  const hasClientFilters = filters.search.trim().length > 0 || entryLevelActive

  // Location is matched server-side so it searches the whole queue rather than
  // whichever page happens to be loaded; debounced so typing doesn't refetch
  // on every keystroke.
  const debouncedLocation = useDebouncedValue(filters.location.trim())

  const jobsQuery = useJobs({
    role_type: mode,
    min_score: filters.minScore || undefined,
    job_family: filters.family === "all" ? undefined : filters.family,
    location: debouncedLocation || undefined,
    sort: filters.sort,
    page_size: hasClientFilters ? 200 : 50,
  })

  const applicationsQuery = useApplications({ role_type: mode, page_size: 200 })
  const applicationByJobId = useMemo(() => {
    const map = new Map<number, number>()
    for (const app of applicationsQuery.data ?? []) map.set(app.job_id, app.id)
    return map
  }, [applicationsQuery.data])

  const queueJob = useQueueJob()
  const prepareJob = usePrepareJob()

  const jobs = useMemo(() => {
    let result = jobsQuery.data ?? []

    if (entryLevelActive) {
      result = result.filter((job) => !SENIOR_TITLE_RE.test(job.title))
    }
    if (filters.targetsOnly) {
      result = result.filter((job) => companyMap.get(job.company_id)?.is_target)
    }
    if (filters.search.trim()) {
      const q = filters.search.trim().toLowerCase()
      result = result.filter((job) => {
        const companyName = companyMap.get(job.company_id)?.name ?? ""
        return job.title.toLowerCase().includes(q) || companyName.toLowerCase().includes(q)
      })
    }
    return result
  }, [jobsQuery.data, filters, companyMap, entryLevelActive])

  function handleQueue(job: Job) {
    queueJob.mutate(job.id, {
      onError: (error) => push({ tone: "error", message: `Could not queue: ${error.message}` }),
    })
  }

  function handlePrepare(job: Job) {
    setPreparingJob(job)
    prepareJob.mutate(
      { id: job.id },
      {
        onError: (error) => {
          const message = error instanceof ApiError ? error.detail : error.message
          push({ tone: "error", message: `Prepare failed: ${message}` })
        },
      },
    )
  }

  useListKeyboardNav({
    items: jobs,
    selectedId,
    onSelect: setSelectedId,
    onOpen: (job) => {
      const appId = applicationByJobId.get(job.id)
      if (appId) navigate(`/applications/${appId}?mode=${mode}`)
    },
    onQueue: handleQueue,
    searchInputRef,
  })

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-(--color-border) px-4 py-3">
        <h1 className="text-(--color-fg-bright) text-sm font-bold tracking-wide">JOB QUEUE</h1>
        <ScanPanel mode={mode} />
      </header>

      <FilterBar filters={filters} onChange={setFilters} searchInputRef={searchInputRef} mode={mode} />
      <ExternalSearchLinks
        family={filters.family}
        location={filters.location}
        roleType={mode}
        search={filters.search}
      />

      {preparingJob && (
        <div className="border-b border-(--color-border) px-4 py-2">
          <PrepareLogPanel
            jobTitle={preparingJob.title}
            isPending={prepareJob.isPending}
            report={prepareJob.data}
            errorMessage={prepareJob.error ? (prepareJob.error instanceof ApiError ? prepareJob.error.detail : prepareJob.error.message) : undefined}
            onClose={() => {
              setPreparingJob(null)
              prepareJob.reset()
            }}
          />
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <Panel className="m-3" bodyClassName="p-0" title={`RESULTS (${jobs.length})`}>
          {jobsQuery.isLoading ? (
            <SkeletonRows />
          ) : jobsQuery.isError ? (
            <EmptyState title="Could not load jobs" hint={jobsQuery.error.message} />
          ) : jobs.length === 0 ? (
            <EmptyState
              title="No jobs match your filters"
              hint={
                (jobsQuery.data?.length ?? 0) === 0
                  ? 'No jobs discovered yet for this mode. Seed target companies in Settings, then hit "SCAN" above.'
                  : "Try widening the score threshold or clearing a filter."
              }
            />
          ) : (
            <QueueTable
              jobs={jobs}
              companyMap={companyMap}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onQueue={handleQueue}
              onPrepare={handlePrepare}
              preparingJobId={preparingJob && prepareJob.isPending ? preparingJob.id : null}
              queuedJobIds={new Set(applicationByJobId.keys())}
            />
          )}
        </Panel>
      </div>
    </div>
  )
}
