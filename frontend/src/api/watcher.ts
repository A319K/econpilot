import { request } from "./client"
import type { CycleSummary, NotifyTestResult, WatcherStatus } from "./types"

export const watcherApi = {
  status: () => request<WatcherStatus>("/watcher/status"),
  runNow: () => request<CycleSummary>("/watcher/run-now", { method: "POST" }),
  notifyTest: () => request<NotifyTestResult>("/notify/test", { method: "POST" }),
}
