import { useQuery } from "@tanstack/react-query"
import { healthApi } from "../api/health"
import { queryKeys } from "./queryKeys"

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: () => healthApi.get(),
    refetchInterval: 15000,
    retry: 1,
  })
}
