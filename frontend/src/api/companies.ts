import { request } from "./client"
import type { Company, CompanyCreate, CompanyUpdate } from "./types"

export const companiesApi = {
  list: () => request<Company[]>("/companies"),

  get: (id: number) => request<Company>(`/companies/${id}`),

  create: (payload: CompanyCreate) => request<Company>("/companies", { method: "POST", body: payload }),

  update: (id: number, payload: CompanyUpdate) =>
    request<Company>(`/companies/${id}`, { method: "PATCH", body: payload }),

  remove: (id: number) => request<void>(`/companies/${id}`, { method: "DELETE" }),
}
