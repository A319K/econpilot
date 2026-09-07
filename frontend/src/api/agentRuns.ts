import { request } from "./client"
import type { AgentRun } from "./types"

export const agentRunsApi = {
  autofill: (applicationId: number) =>
    request<AgentRun>(`/applications/${applicationId}/autofill`, { method: "POST" }),

  get: (runId: number) => request<AgentRun>(`/agent-runs/${runId}`),

  resume: (runId: number) => request<AgentRun>(`/agent-runs/${runId}/resume`, { method: "POST" }),

  abandon: (runId: number) => request<AgentRun>(`/agent-runs/${runId}/abandon`, { method: "POST" }),
}
