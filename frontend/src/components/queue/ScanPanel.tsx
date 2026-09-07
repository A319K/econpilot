import { useState } from "react"
import type { ScanReport } from "../../api/types"
import { useScan } from "../../hooks/useScan"
import type { Mode } from "../../lib/mode"
import { formatTimestamp } from "../../lib/format"
import { Button } from "../ui/Button"
import { type LogLine, ProgressLog } from "../ui/ProgressLog"
import { Spinner } from "../ui/Spinner"
import { useToast } from "../ui/Toast"

// Per-company fetch errors are expected noise from a large, self-expanding
// corpus (stale/guessed ATS coordinates, throttling). Rather than dump one line
// per company, bucket them by cause so the report stays readable.
const ERROR_BUCKETS: { label: string; match: (e: string) => boolean }[] = [
  { label: "not found (404 — board moved/removed)", match: (e) => /status 404\b/.test(e) },
  { label: "wrong Workday site (422)", match: (e) => /status 422\b/.test(e) },
  { label: "rate-limited (429 — retried, still busy)", match: (e) => /status 429\b/.test(e) },
  { label: "blocked (403)", match: (e) => /status 403\b/.test(e) },
  { label: "invalid response (not JSON)", match: (e) => /not JSON/i.test(e) },
]

function summarizeErrors(errors: string[]): { label: string; count: number }[] {
  const counts = ERROR_BUCKETS.map((b) => ({ label: b.label, count: 0 }))
  let other = 0
  for (const error of errors) {
    const idx = ERROR_BUCKETS.findIndex((b) => b.match(error))
    if (idx === -1) other += 1
    else counts[idx].count += 1
  }
  if (other > 0) counts.push({ label: "other", count: other })
  return counts.filter((c) => c.count > 0)
}

function reportToLines(report: ScanReport): LogLine[] {
  const now = formatTimestamp(new Date().toISOString())
  const lines: LogLine[] = [
    { timestamp: now, text: `companies scanned: ${report.companies_scanned}` },
    { timestamp: now, text: `jobs found: ${report.jobs_found}` },
    { timestamp: now, text: `new: ${report.new}`, tone: "success" },
    { timestamp: now, text: `duplicates: ${report.duplicates}` },
  ]
  if (report.resolved_companies) {
    lines.push({
      timestamp: now,
      text: `newly resolved companies: ${report.resolved_companies}`,
      tone: "success",
    })
  }
  if (report.errors.length > 0) {
    lines.push({
      timestamp: now,
      text: `${report.errors.length} companies skipped (unreachable — harmless):`,
      tone: "error",
    })
    for (const { label, count } of summarizeErrors(report.errors)) {
      lines.push({ timestamp: now, text: `  · ${label}: ${count}`, tone: "error" })
    }
  }
  return lines
}

export function ScanPanel({ mode }: { mode: Mode }) {
  const scan = useScan()
  const { push } = useToast()
  const [dismissed, setDismissed] = useState(false)

  function runScan() {
    setDismissed(false)
    scan.mutate(
      { role_type: mode, targets_only: false },
      {
        onError: (error) => {
          push({ tone: "error", message: `Scan failed: ${error.message}` })
        },
      },
    )
  }

  const showReport = scan.data && !dismissed

  return (
    <div className="flex flex-col gap-2">
      <Button variant="primary" onClick={runScan} disabled={scan.isPending}>
        {scan.isPending ? (
          <span className="flex items-center gap-1.5">
            <Spinner /> scanning…
          </span>
        ) : (
          "SCAN"
        )}
      </Button>

      {showReport && scan.data && (
        <div className="relative w-80">
          <ProgressLog lines={reportToLines(scan.data)} />
          <button
            onClick={() => setDismissed(true)}
            className="text-(--color-fg-dim) hover:text-(--color-fg-bright) absolute right-1 top-1 text-xs"
            aria-label="Dismiss scan report"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  )
}
