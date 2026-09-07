import { request } from "./client"
import type { ScanReport, ScanRequest } from "./types"

export const scanApi = {
  run: (payload: ScanRequest = {}) => request<ScanReport>("/scan", { method: "POST", body: payload }),
}
