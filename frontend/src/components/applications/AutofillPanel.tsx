import { useState } from "react"
import type { AgentActionLogEntry, AgentRun, ApplicationDetail, PauseReason } from "../../api/types"
import { formatTimestamp } from "../../lib/format"
import { Button } from "../ui/Button"
import { type LogLine, ProgressLog } from "../ui/ProgressLog"
import { useToast } from "../ui/Toast"
import { useAbandonRun, useAgentRun, useResumeRun, useStartAutofill } from "../../hooks/useAgentRun"

const AUTOFILL_STATUSES = new Set<ApplicationDetail["status"]>(["queued", "in_progress"])

const PAUSE_REASON_LABEL: Record<PauseReason, string> = {
  login_required: "a login / signup wall - log in yourself in the open browser",
  captcha: "a CAPTCHA - solve it in the open browser",
  unmapped_required_field: "a required field it couldn't answer - fill it in the open browser",
  cap_exceeded: "a safety cap (actions/steps/LLM/time) was reached",
  error: "an unexpected error",
}

function tsOf(entry: AgentActionLogEntry): string {
  const ts = entry.ts
  return typeof ts === "number" ? formatTimestamp(new Date(ts * 1000).toISOString()) : ""
}

function formatEntry(entry: AgentActionLogEntry): LogLine {
  const timestamp = tsOf(entry)

  if (typeof entry.event === "string") {
    const event = entry.event
    const detail = entry.detail ?? entry.reason ?? entry.url ?? entry.step ?? ""
    let tone: LogLine["tone"] = "default"
    if (event === "review_reached") tone = "success"
    else if (event === "pause" || event === "error" || event === "review_rejected") tone = "error"
    return { timestamp, text: `${event}${detail ? `: ${detail}` : ""}`, tone }
  }

  if (typeof entry.action === "string") {
    const parts = [entry.action]
    if (entry.ref) parts.push(`ref=${entry.ref}`)
    if (entry.value !== undefined && entry.value !== null) parts.push(`= ${String(entry.value)}`)
    const result = String(entry.result ?? "")
    const source = entry.source ? ` [${entry.source}]` : ""
    const tone: LogLine["tone"] =
      result === "blocked" || result === "rejected" ? "error" : result === "ok" ? "success" : "default"
    const note = entry.note ? ` — ${entry.note}` : ""
    return { timestamp, text: `${parts.join(" ")}${source} → ${result || "?"}${note}`, tone }
  }

  return { timestamp, text: JSON.stringify(entry) }
}

function runLines(run: AgentRun | undefined): LogLine[] {
  if (!run) return []
  const lines = (run.action_log ?? []).map(formatEntry)
  if (run.status === "ready_for_review") {
    lines.push({
      timestamp: "",
      text: "Review the open browser window and submit manually.",
      tone: "success",
    })
  } else if (run.status === "paused" && run.pause_reason) {
    lines.push({ timestamp: "", text: `paused: ${PAUSE_REASON_LABEL[run.pause_reason]}`, tone: "error" })
  } else if (run.status === "failed") {
    lines.push({ timestamp: "", text: "run failed — see log above", tone: "error" })
  } else if (run.status === "abandoned") {
    lines.push({ timestamp: "", text: "run abandoned", tone: "default" })
  }
  return lines
}

export function AutofillPanel({ application }: { application: ApplicationDetail }) {
  const { push } = useToast()
  const [runId, setRunId] = useState<number | undefined>(undefined)

  const start = useStartAutofill(application.id)
  const resume = useResumeRun(application.id)
  const abandon = useAbandonRun(application.id)
  const runQuery = useAgentRun(runId)
  const run = runQuery.data

  const canAutofill =
    AUTOFILL_STATUSES.has(application.status) && !!application.resume_version?.pdf_path
  const isActive = run?.status === "running" || run?.status === "paused"

  function onStart() {
    start.mutate(application.id, {
      onSuccess: (created) => setRunId(created.id),
      onError: (error) => push({ tone: "error", message: `Autofill failed to start: ${error.message}` }),
    })
  }

  if (!runId) {
    return (
      <div className="text-xs">
        {canAutofill ? (
          <>
            <p className="text-(--color-fg-dim) mb-2">
              Open this job's application page in a browser and fill it from your profile. The agent
              stops at the review step — it never submits.
            </p>
            <Button variant="primary" onClick={onStart} disabled={start.isPending}>
              {start.isPending ? "starting…" : "autofill application"}
            </Button>
          </>
        ) : (
          <p className="text-(--color-fg-dim)">
            Autofill needs status queued/in_progress and a prepared resume PDF — run Prepare from the
            Queue view first.
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <ProgressLog lines={runLines(run)} className="max-h-72 overflow-y-auto" />

      {run?.status === "paused" && (
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            disabled={resume.isPending}
            onClick={() =>
              resume.mutate(run.id, {
                onError: (e) => push({ tone: "error", message: `Resume failed: ${e.message}` }),
              })
            }
          >
            resume
          </Button>
          <Button
            variant="danger"
            disabled={abandon.isPending}
            onClick={() =>
              abandon.mutate(run.id, {
                onError: (e) => push({ tone: "error", message: `Abandon failed: ${e.message}` }),
              })
            }
          >
            abandon
          </Button>
          <span className="text-(--color-fg-faint) text-xs">
            fix the blocker in the open browser, then resume
          </span>
        </div>
      )}

      {isActive && run?.status === "running" && (
        <p className="text-(--color-fg-faint) text-xs">agent working — {run.llm_calls} llm call(s)…</p>
      )}
    </div>
  )
}
