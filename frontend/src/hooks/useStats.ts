import { useQuery } from "@tanstack/react-query"
import { statsApi } from "../api/stats"
import { queryKeys } from "./queryKeys"

export function useStats() {
  return useQuery({
    queryKey: queryKeys.stats(),
    queryFn: () => statsApi.get(),
  })
}
