import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { agentRunsApi } from "../api/agentRuns"
import type { AgentRun } from "../api/types"
import { queryKeys } from "./queryKeys"

// A run is "active" while it holds the browser (running or paused) - poll it.
const ACTIVE_STATUSES = new Set<AgentRun["status"]>(["running", "paused"])
const POLL_INTERVAL_MS = 2000

export function useAgentRun(runId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.agentRun(runId ?? -1),
    queryFn: () => agentRunsApi.get(runId as number),
    enabled: runId !== undefined,
    // Live terminal readout: poll every 2s while the run is active, then stop.
    refetchInterval: (query) => {
      const data = query.state.data as AgentRun | undefined
      return data && ACTIVE_STATUSES.has(data.status) ? POLL_INTERVAL_MS : false
    },
  })
}

export function useStartAutofill(applicationId?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => agentRunsApi.autofill(id),
    onSuccess: (run) => {
      queryClient.setQueryData(queryKeys.agentRun(run.id), run)
      if (applicationId !== undefined) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.application(applicationId) })
      }
    },
  })
}

export function useResumeRun(applicationId?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: number) => agentRunsApi.resume(runId),
    onSuccess: (run) => queryClient.setQueryData(queryKeys.agentRun(run.id), run),
    onSettled: () => {
      if (applicationId !== undefined) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.application(applicationId) })
      }
    },
  })
}

export function useAbandonRun(applicationId?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: number) => agentRunsApi.abandon(runId),
    onSuccess: (run) => queryClient.setQueryData(queryKeys.agentRun(run.id), run),
    onSettled: () => {
      if (applicationId !== undefined) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.application(applicationId) })
      }
    },
  })
}
