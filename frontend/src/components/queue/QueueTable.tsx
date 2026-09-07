import type { Company, Job } from "../../api/types"
import { formatAge } from "../../lib/format"
import { Button } from "../ui/Button"
import { ScoreBar } from "../ui/ScoreBar"
import { Spinner } from "../ui/Spinner"

function scoreBreakdownTitle(job: Job): string | undefined {
  if (!job.score_breakdown) return undefined
  return Object.entries(job.score_breakdown)
    .filter(([, v]) => typeof v === "number")
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n")
}

interface QueueTableProps {
  jobs: Job[]
  companyMap: Map<number, Company>
  selectedId: number | null
  onSelect: (id: number) => void
  onQueue: (job: Job) => void
  onPrepare: (job: Job) => void
  preparingJobId: number | null
  queuedJobIds: Set<number>
}

export function QueueTable({
  jobs,
  companyMap,
  selectedId,
  onSelect,
  onQueue,
  onPrepare,
  preparingJobId,
  queuedJobIds,
}: QueueTableProps) {
  return (
    <table className="w-full border-collapse text-xs">
      <thead>
        <tr className="text-(--color-fg-dim) border-b border-(--color-border) text-left">
          <th className="w-6 px-2 py-1.5" aria-hidden="true"></th>
          <th className="px-2 py-1.5 font-normal">score</th>
          <th className="px-2 py-1.5 font-normal">title</th>
          <th className="px-2 py-1.5 font-normal">company</th>
          <th className="px-2 py-1.5 font-normal">family</th>
          <th className="px-2 py-1.5 font-normal">location</th>
          <th className="px-2 py-1.5 font-normal">age</th>
          <th className="px-2 py-1.5 font-normal">source</th>
          <th className="px-2 py-1.5 font-normal">actions</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((job) => {
          const company = companyMap.get(job.company_id)
          const selected = job.id === selectedId
          const isQueued = queuedJobIds.has(job.id)
          const isPreparing = preparingJobId === job.id

          return (
            <tr
              key={job.id}
              onClick={() => onSelect(job.id)}
              className={`cursor-pointer border-b border-(--color-border-dim) ${
                selected ? "bg-(--color-accent-bg) border-l-2 border-l-(--color-accent)" : "border-l-2 border-l-transparent"
              }`}
            >
              <td className="px-2 py-1.5 text-(--color-accent)">{selected ? "▸" : ""}</td>
              <td className="px-2 py-1.5" title={scoreBreakdownTitle(job)}>
                <ScoreBar score={job.score} />
              </td>
              <td className="max-w-64 truncate px-2 py-1.5 text-(--color-fg-bright)" title={job.title}>
                {job.title}
              </td>
              <td className="px-2 py-1.5">
                {company?.is_target && (
                  <span className="text-(--color-accent) mr-1" aria-label="target company">
                    ★
                  </span>
                )}
                {company?.name ?? `#${job.company_id}`}
              </td>
              <td className="px-2 py-1.5 text-(--color-fg-dim)">{job.job_family}</td>
              <td className="max-w-32 truncate px-2 py-1.5 text-(--color-fg-dim)" title={job.location ?? ""}>
                {job.location ?? "—"}
              </td>
              <td className="text-(--color-fg-dim) px-2 py-1.5 tabular-nums">
                {formatAge(job.posted_at ?? job.discovered_at)}
              </td>
              <td className="text-(--color-fg-dim) px-2 py-1.5">{job.source}</td>
              <td className="px-2 py-1.5">
                <div className="flex items-center gap-1.5">
                  <Button
                    variant={isQueued ? "ghost" : "primary"}
                    disabled={isQueued}
                    onClick={(e) => {
                      e.stopPropagation()
                      onQueue(job)
                    }}
                  >
                    {isQueued ? "queued" : "queue"}
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={isPreparing}
                    onClick={(e) => {
                      e.stopPropagation()
                      onPrepare(job)
                    }}
                  >
                    {isPreparing ? <Spinner /> : "prepare"}
                  </Button>
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-(--color-fg-dim) hover:text-(--color-accent) px-1"
                    aria-label="Open posting"
                  >
                    ↗
                  </a>
                </div>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
