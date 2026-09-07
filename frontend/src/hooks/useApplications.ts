import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { applicationsApi } from "../api/applications"
import type { ApplicationDetail, ApplicationListItem, ApplicationListParams, NotesUpdate, StatusUpdate } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useApplications(params: ApplicationListParams) {
  return useQuery({
    queryKey: queryKeys.applications(params),
    queryFn: () => applicationsApi.list(params),
    placeholderData: (previous) => previous,
  })
}

export function useApplication(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.application(id ?? -1),
    queryFn: () => applicationsApi.get(id as number),
    enabled: id !== undefined,
  })
}

interface UpdateStatusContext {
  previousLists: [readonly unknown[], ApplicationListItem[] | undefined][]
}

/** Optimistically moves the application to its new status everywhere it
 * appears in cached application lists (e.g. kanban columns), and rolls the
 * cache back if the server rejects the transition (409 on an invalid move). */
export function useUpdateApplicationStatus() {
  const queryClient = useQueryClient()

  return useMutation<ApplicationDetail, Error, { id: number; payload: StatusUpdate }, UpdateStatusContext>({
    mutationFn: ({ id, payload }) => applicationsApi.updateStatus(id, payload),
    onMutate: async ({ id, payload }) => {
      await queryClient.cancelQueries({ queryKey: ["applications"] })

      const previousLists = queryClient.getQueriesData<ApplicationListItem[]>({ queryKey: ["applications"] })

      for (const [key, data] of previousLists) {
        if (!data) continue
        queryClient.setQueryData<ApplicationListItem[]>(
          key,
          data.map((application) =>
            application.id === id ? { ...application, status: payload.status } : application,
          ),
        )
      }

      return { previousLists }
    },
    onError: (_error, _variables, context) => {
      if (!context) return
      for (const [key, data] of context.previousLists) {
        queryClient.setQueryData(key, data)
      }
    },
    onSettled: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["applications"] })
      void queryClient.invalidateQueries({ queryKey: ["stats"] })
      if (data) {
        queryClient.setQueryData(queryKeys.application(data.id), data)
      }
    },
  })
}

export function useUpdateApplicationNotes() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: NotesUpdate }) =>
      applicationsApi.updateNotes(id, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.application(data.id), data)
    },
  })
}

export function useQueueJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: number) => applicationsApi.queueJob(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["applications"] })
      void queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
  })
}

export function useDeleteApplication() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => applicationsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["applications"] })
      void queryClient.invalidateQueries({ queryKey: ["stats"] })
    },
  })
}
