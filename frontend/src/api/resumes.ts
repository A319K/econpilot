import { request } from "./client"
import type { ResumeVersion, ResumeVersionCreate, ResumeVersionUpdate } from "./types"

export const resumesApi = {
  list: () => request<ResumeVersion[]>("/resumes"),

  get: (id: number) => request<ResumeVersion>(`/resumes/${id}`),

  create: (payload: ResumeVersionCreate) =>
    request<ResumeVersion>("/resumes", { method: "POST", body: payload }),

  update: (id: number, payload: ResumeVersionUpdate) =>
    request<ResumeVersion>(`/resumes/${id}`, { method: "PUT", body: payload }),

  remove: (id: number) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
}
