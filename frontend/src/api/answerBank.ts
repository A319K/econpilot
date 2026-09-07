import { request } from "./client"
import type { AnswerBankCreate, AnswerBankEntry, AnswerBankUpdate, AnswerSource } from "./types"

export interface AnswerBankListParams {
  approved?: boolean
  source?: AnswerSource
}

export const answerBankApi = {
  list: (params: AnswerBankListParams = {}) =>
    request<AnswerBankEntry[]>("/answer-bank", { params: { ...params } }),

  create: (payload: AnswerBankCreate) =>
    request<AnswerBankEntry>("/answer-bank", { method: "POST", body: payload }),

  update: (id: number, payload: AnswerBankUpdate) =>
    request<AnswerBankEntry>(`/answer-bank/${id}`, { method: "PATCH", body: payload }),

  remove: (id: number) => request<void>(`/answer-bank/${id}`, { method: "DELETE" }),
}
