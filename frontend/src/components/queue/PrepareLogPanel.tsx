import { useEffect, useState } from "react"
import type { PrepareReport } from "../../api/types"
import { formatTimestamp } from "../../lib/format"
import { type LogLine, ProgressLog } from "../ui/ProgressLog"

// prepare_materials runs these steps server-side, in order, but the API is a
// single request/response (no SSE) - we surface a plausible step sequence
// while the request is in flight, then reconcile with the real report.
// Select-only is the default (no per-job rewrite); the real report reconciles
// and shows "tailored" when a caller opts into tailoring for a specific job.
const STEPS = [
  "extracting JD keywords…",
  "selecting best-fit resume…",
  "drafting cover letter…",
  "compiling PDFs…",
]
const STEP_INTERVAL_MS = 3500

export function PrepareLogPanel({
  jobTitle,
  isPending,
  report,
  errorMessage,
  onClose,
}: {
  jobTitle: string
  isPending: boolean
  report?: PrepareReport
  errorMessage?: string
  onClose: () => void
}) {
  const [stepIndex, setStepIndex] = useState(0)

  useEffect(() => {
    if (!isPending) return
    setStepIndex(0)
    const id = setInterval(() => {
      setStepIndex((i) => Math.min(STEPS.length - 1, i + 1))
    }, STEP_INTERVAL_MS)
    return () => clearInterval(id)
  }, [isPending])

  const now = () => formatTimestamp(new Date().toISOString())

  const lines: LogLine[] = [{ timestamp: now(), text: `preparing materials for "${jobTitle}"` }]

  if (isPending) {
    for (let i = 0; i <= stepIndex; i++) {
      lines.push({ timestamp: now(), text: STEPS[i] })
    }
  } else if (errorMessage) {
    lines.push({ timestamp: now(), text: errorMessage, tone: "error" })
  } else if (report) {
    lines.push({
      timestamp: now(),
      text: `resume #${report.resume_used}${report.tailored ? ` tailored (${report.regions_changed.join(", ")})` : " (no tailoring)"}`,
      tone: "success",
    })
    if (report.cover_letter_id !== null) {
      lines.push({ timestamp: now(), text: `cover letter #${report.cover_letter_id} drafted`, tone: "success" })
    }
    for (const [kind, path] of Object.entries(report.pdf_paths)) {
      lines.push({ timestamp: now(), text: `${kind} pdf: ${path}` })
    }
    lines.push({ timestamp: now(), text: `${report.llm_calls_made} llm call(s) made`, tone: "success" })
  }

  return (
    <div className="relative w-96">
      <ProgressLog lines={lines} />
      {!isPending && (
        <button
          onClick={onClose}
          className="text-(--color-fg-dim) hover:text-(--color-fg-bright) absolute right-1 top-1 text-xs"
          aria-label="Dismiss prepare log"
        >
          ✕
        </button>
      )}
    </div>
  )
}
