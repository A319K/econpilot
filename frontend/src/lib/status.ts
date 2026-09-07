import type { ApplicationStatus } from "../api/types"

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  discovered: "DISCOVERED",
  queued: "QUEUED",
  in_progress: "IN_PROGRESS",
  ready_to_submit: "READY",
  submitted: "SUBMITTED",
  oa: "OA",
  interview: "INTERVIEW",
  offer: "OFFER",
  rejected: "REJECTED",
  withdrawn: "WITHDRAWN",
}

// Tailwind arbitrary-value friendly var() references, matching index.css tokens.
export const STATUS_COLOR_VAR: Record<ApplicationStatus, string> = {
  discovered: "var(--color-status-discovered)",
  queued: "var(--color-status-queued)",
  in_progress: "var(--color-status-in-progress)",
  ready_to_submit: "var(--color-status-ready)",
  submitted: "var(--color-status-submitted)",
  oa: "var(--color-status-oa)",
  interview: "var(--color-status-interview)",
  offer: "var(--color-status-offer)",
  rejected: "var(--color-status-rejected)",
  withdrawn: "var(--color-status-withdrawn)",
}

export const KANBAN_STATUSES: ApplicationStatus[] = [
  "queued",
  "in_progress",
  "ready_to_submit",
  "submitted",
  "oa",
  "interview",
  "offer",
  "rejected",
]

export function scoreTierColor(score: number): string {
  if (score >= 70) return "var(--color-tier-high)"
  if (score >= 40) return "var(--color-tier-mid)"
  return "var(--color-tier-low)"
}
