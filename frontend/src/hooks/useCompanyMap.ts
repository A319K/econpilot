import { useMemo } from "react"
import type { Company } from "../api/types"
import { useCompanies } from "./useCompanies"

export function useCompanyMap(): Map<number, Company> {
  const { data } = useCompanies()
  return useMemo(() => new Map((data ?? []).map((c) => [c.id, c])), [data])
}
