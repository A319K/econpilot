import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { companiesApi } from "../api/companies"
import type { CompanyCreate, CompanyUpdate } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useCompanies() {
  return useQuery({
    queryKey: queryKeys.companies(),
    queryFn: () => companiesApi.list(),
  })
}

export function useCreateCompany() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CompanyCreate) => companiesApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.companies() })
    },
  })
}

export function useUpdateCompany() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CompanyUpdate }) =>
      companiesApi.update(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.companies() })
    },
  })
}

export function useDeleteCompany() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => companiesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.companies() })
    },
  })
}
