export function formatAge(isoDate: string | null): string {
  if (!isoDate) return "—"
  const then = new Date(isoDate).getTime()
  const now = Date.now()
  const diffMs = Math.max(0, now - then)
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d`
  const months = Math.floor(days / 30)
  return `${months}mo`
}

export function formatDaysInStage(isoDate: string): number {
  const then = new Date(isoDate).getTime()
  return Math.max(0, Math.floor((Date.now() - then) / 86_400_000))
}

export function formatTimestamp(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

export function formatHours(hours: number | null): string {
  if (hours === null) return "—"
  if (hours < 24) return `${hours.toFixed(1)}h`
  return `${(hours / 24).toFixed(1)}d`
}

export function slugifyFilename(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
}
