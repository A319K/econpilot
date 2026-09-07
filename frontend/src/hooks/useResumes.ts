import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { resumesApi } from "../api/resumes"
import type { JobFamily, ResumeVersionCreate, ResumeVersionUpdate } from "../api/types"
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

export function useUploadResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, name, jobFamily }: { file: File; name: string; jobFamily: JobFamily }) =>
      resumesApi.upload(file, name, jobFamily),
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
