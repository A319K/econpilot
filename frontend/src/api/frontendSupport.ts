import { request } from "./client"

export interface JobKeywordsResponse {
  jd_keywords: Record<string, string[]> | null
}

export const frontendSupportApi = {
  getJobKeywords: (jobId: number) => request<JobKeywordsResponse>(`/frontend-support/jobs/${jobId}/keywords`),
}
