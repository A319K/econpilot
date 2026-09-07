import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { coverLettersApi } from "../api/coverLetters"
import type { CoverLetterReview, CoverLetterUpdate } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useCoverLetter(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.coverLetter(id ?? -1),
    queryFn: () => coverLettersApi.get(id as number),
    enabled: id !== undefined,
  })
}

export function useUpdateCoverLetter(applicationId?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CoverLetterUpdate }) =>
      coverLettersApi.update(id, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.coverLetter(data.id), data)
      if (applicationId !== undefined) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.application(applicationId) })
      }
    },
  })
}

export function useReviewCoverLetter(applicationId?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CoverLetterReview }) =>
      coverLettersApi.review(id, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.coverLetter(data.id), data)
      if (applicationId !== undefined) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.application(applicationId) })
      }
    },
  })
}
