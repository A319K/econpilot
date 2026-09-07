import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { jobsApi } from "../api/jobs"
import type { JobListParams, ManualJobCreate, PrepareRequest } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useJobs(params: JobListParams) {
  return useQuery({
    queryKey: queryKeys.jobs(params),
    queryFn: () => jobsApi.list(params),
    placeholderData: (previous) => previous,
  })
}

export function useJob(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.job(id ?? -1),
    queryFn: () => jobsApi.get(id as number),
    enabled: id !== undefined,
  })
}

export function useCreateManualJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ManualJobCreate) => jobsApi.createManual(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
  })
}

export function usePrepareJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload?: PrepareRequest }) =>
      jobsApi.prepare(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["applications"] })
      void queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
  })
}
