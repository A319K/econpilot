import { request } from "./client"
import type { CoverLetter, CoverLetterReview, CoverLetterUpdate } from "./types"

export const coverLettersApi = {
  get: (id: number) => request<CoverLetter>(`/cover-letters/${id}`),

  update: (id: number, payload: CoverLetterUpdate) =>
    request<CoverLetter>(`/cover-letters/${id}`, { method: "PUT", body: payload }),

  review: (id: number, payload: CoverLetterReview) =>
    request<CoverLetter>(`/cover-letters/${id}`, { method: "PATCH", body: payload }),
}
