import { request } from "./client"
import type {
  ApplicationDetail,
  ApplicationListItem,
  ApplicationListParams,
  NotesUpdate,
  StatusUpdate,
} from "./types"

export const applicationsApi = {
  list: (params: ApplicationListParams = {}) =>
    request<ApplicationListItem[]>("/applications", { params: { ...params } }),

  get: (id: number) => request<ApplicationDetail>(`/applications/${id}`),

  updateStatus: (id: number, payload: StatusUpdate) =>
    request<ApplicationDetail>(`/applications/${id}/status`, { method: "PATCH", body: payload }),

  updateNotes: (id: number, payload: NotesUpdate) =>
    request<ApplicationDetail>(`/applications/${id}/notes`, { method: "PATCH", body: payload }),

  queueJob: (jobId: number) => request<ApplicationDetail>(`/jobs/${jobId}/queue`, { method: "POST" }),

  remove: (id: number) => request<void>(`/applications/${id}`, { method: "DELETE" }),
}
