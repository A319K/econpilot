import { request, requestForm } from "./client"
import type { JobFamily, ResumeVersion, ResumeVersionCreate, ResumeVersionUpdate } from "./types"

export const resumesApi = {
  list: () => request<ResumeVersion[]>("/resumes"),

  get: (id: number) => request<ResumeVersion>(`/resumes/${id}`),

  create: (payload: ResumeVersionCreate) =>
    request<ResumeVersion>("/resumes", { method: "POST", body: payload }),

  update: (id: number, payload: ResumeVersionUpdate) =>
    request<ResumeVersion>(`/resumes/${id}`, { method: "PUT", body: payload }),

  upload: (file: File, name: string, jobFamily: JobFamily) => {
    const form = new FormData()
    form.append("file", file)
    form.append("name", name)
    form.append("job_family", jobFamily)
    return requestForm<ResumeVersion>("/resumes/upload", form)
  },

  remove: (id: number) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
}
