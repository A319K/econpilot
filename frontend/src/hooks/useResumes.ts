import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { resumesApi } from "../api/resumes"
import type { ResumeVersionCreate, ResumeVersionUpdate } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useResumes() {
  return useQuery({
    queryKey: queryKeys.resumes(),
    queryFn: () => resumesApi.list(),
  })
}

export function useCreateResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ResumeVersionCreate) => resumesApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.resumes() })
    },
  })
}

export function useUpdateResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ResumeVersionUpdate }) =>
      resumesApi.update(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.resumes() })
    },
  })
}

export function useDeleteResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => resumesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.resumes() })
    },
  })
}
