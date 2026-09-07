import { useEffect, useState } from "react"
import { formatTimestamp } from "../../lib/format"
import { useNotifyTest, useWatcherRunNow, useWatcherStatus } from "../../hooks/useWatcher"
import { Button } from "../ui/Button"
import { type LogLine, ProgressLog } from "../ui/ProgressLog"
import { Spinner } from "../ui/Spinner"

function useCountdown(nextRunAt: string | null): string {
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!nextRunAt) return
    const id = setInterval(() => setTick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [nextRunAt])

  if (!nextRunAt) return "—"
  const diffMs = new Date(nextRunAt).getTime() - Date.now()
  if (diffMs <= 0) return "now"
  const totalSeconds = Math.floor(diffMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`
}

export function WatcherPanel() {
  const { data: status } = useWatcherStatus()
  const runNow = useWatcherRunNow()
  const notifyTest = useNotifyTest()
  const [logLines, setLogLines] = useState<LogLine[]>([])
  const countdown = useCountdown(status?.next_run_at ?? null)

  function appendLog(text: string, tone?: LogLine["tone"]) {
    setLogLines((lines) => [...lines, { timestamp: formatTimestamp(new Date().toISOString()), text, tone }])
  }

  function handleRunNow() {
    runNow.mutate(undefined, {
      onSuccess: (report) => {
        appendLog(
          `cycle complete: ${report.companies} companies, ${report.new_jobs} new, ${report.deactivated} deactivated, ${report.notified} notified`,
          "success",
        )
        for (const error of report.errors) appendLog(`error: ${error}`, "error")
      },
      onError: (error) => appendLog(`run-now failed: ${error.message}`, "error"),
    })
  }

  function handleSendTest() {
    notifyTest.mutate(undefined, {
      onSuccess: (result) =>
        appendLog(
          `test notification via ${result.adapter}: ${result.success ? "sent" : "failed"}`,
          result.success ? "success" : "error",
        ),
      onError: (error) => appendLog(`notify test failed: ${error.message}`, "error"),
    })
  }

  const enabled = status?.enabled ?? false
  const lastCycle = status?.last_cycle

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-xs">
        <span
          className={`inline-block h-2 w-2 rounded-full ${enabled ? "bg-(--color-accent)" : "bg-(--color-fg-faint)"}`}
        />
        <span className="text-(--color-fg-bright) font-medium">{enabled ? "ENABLED" : "DISABLED"}</span>
        {status?.running && (
          <span className="text-(--color-fg-dim) flex items-center gap-1">
            <Spinner /> running…
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="text-(--color-fg-dim)">next run</div>
        <div className="text-(--color-fg)">{enabled ? countdown : "—"}</div>

        <div className="text-(--color-fg-dim)">last cycle</div>
        <div className="text-(--color-fg)">
          {lastCycle
            ? `${formatTimestamp(lastCycle.started)} · ${lastCycle.new_jobs} new · ${lastCycle.deactivated} deactivated · ${lastCycle.notified} notified${
                lastCycle.errors.length ? ` · ${lastCycle.errors.length} errors` : ""
              }`
            : "never run"}
        </div>
      </div>

      <div className="flex gap-2">
        <Button variant="primary" onClick={handleRunNow} disabled={runNow.isPending || status?.running}>
          {runNow.isPending ? (
            <span className="flex items-center gap-1.5">
              <Spinner /> running…
            </span>
          ) : (
            "RUN NOW"
          )}
        </Button>
        <Button variant="ghost" onClick={handleSendTest} disabled={notifyTest.isPending}>
          {notifyTest.isPending ? "sending…" : "SEND TEST NOTIFICATION"}
        </Button>
      </div>

      {logLines.length > 0 && <ProgressLog lines={logLines} className="max-h-40 overflow-y-auto" />}
    </div>
  )
}
