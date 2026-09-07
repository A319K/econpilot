import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { answerBankApi } from "../api/answerBank"
import type { AnswerBankCreate, AnswerBankUpdate } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useAnswerBank() {
  return useQuery({
    queryKey: queryKeys.answerBank(),
    queryFn: () => answerBankApi.list(),
  })
}

function useInvalidate() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.answerBank() })
}

export function useCreateAnswer() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (payload: AnswerBankCreate) => answerBankApi.create(payload),
    onSuccess: () => void invalidate(),
  })
}

export function useUpdateAnswer() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AnswerBankUpdate }) =>
      answerBankApi.update(id, payload),
    onSuccess: () => void invalidate(),
  })
}

export function useDeleteAnswer() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (id: number) => answerBankApi.remove(id),
    onSuccess: () => void invalidate(),
  })
}
