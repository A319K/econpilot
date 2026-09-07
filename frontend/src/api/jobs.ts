import { request } from "./client"
import type { Job, JobListParams, ManualJobCreate, PrepareReport, PrepareRequest } from "./types"

export const jobsApi = {
  list: (params: JobListParams = {}) => request<Job[]>("/jobs", { params: { ...params } }),

  get: (id: number) => request<Job>(`/jobs/${id}`),

  createManual: (payload: ManualJobCreate) =>
    request<Job>("/jobs/manual", { method: "POST", body: payload }),

  prepare: (id: number, payload: PrepareRequest = {}) =>
    request<PrepareReport>(`/jobs/${id}/prepare`, { method: "POST", body: payload }),
}
