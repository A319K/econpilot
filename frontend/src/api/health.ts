import { request } from "./client"
import type { HealthResponse } from "./types"

export const healthApi = {
  get: () => request<HealthResponse>("/health"),
}
