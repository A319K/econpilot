import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { watcherApi } from "../api/watcher"
import { queryKeys } from "./queryKeys"

export function useWatcherStatus() {
  return useQuery({
    queryKey: queryKeys.watcherStatus(),
    queryFn: () => watcherApi.status(),
    refetchInterval: 30000,
    retry: 1,
  })
}

export function useWatcherRunNow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => watcherApi.runNow(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.watcherStatus() })
      void queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
  })
}

export function useNotifyTest() {
  return useMutation({
    mutationFn: () => watcherApi.notifyTest(),
  })
}
