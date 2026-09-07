import type { ApplicationListParams, JobListParams } from "../api/types"

export const queryKeys = {
  jobs: (params: JobListParams) => ["jobs", params] as const,
  job: (id: number) => ["jobs", id] as const,
  applications: (params: ApplicationListParams) => ["applications", params] as const,
  application: (id: number) => ["applications", id] as const,
  stats: () => ["stats"] as const,
  companies: () => ["companies"] as const,
  resumes: () => ["resumes"] as const,
  coverLetter: (id: number) => ["cover-letters", id] as const,
  agentRun: (id: number) => ["agent-runs", id] as const,
  answerBank: () => ["answer-bank"] as const,
  health: () => ["health"] as const,
  watcherStatus: () => ["watcher-status"] as const,
}
