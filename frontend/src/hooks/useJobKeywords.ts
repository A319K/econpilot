import { useQuery } from "@tanstack/react-query"
import { frontendSupportApi } from "../api/frontendSupport"

export function useJobKeywords(jobId: number | undefined) {
  return useQuery({
    queryKey: ["job-keywords", jobId],
    queryFn: () => frontendSupportApi.getJobKeywords(jobId as number),
    enabled: jobId !== undefined,
  })
}
