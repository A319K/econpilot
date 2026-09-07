import { request } from "./client"
import type { StatsResponse } from "./types"

export const statsApi = {
  get: () => request<StatsResponse>("/stats"),
}
