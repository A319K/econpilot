export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.clone().json()) as { detail?: unknown }
    if (typeof body.detail === "string") return body.detail
    if (body.detail) return JSON.stringify(body.detail)
  } catch {
    // response wasn't JSON; fall through to status text
  }
  return response.statusText || `Request failed with status ${response.status}`
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  params?: Record<string, string | number | boolean | string[] | undefined>
}

function buildQuery(params?: RequestOptions["params"]): string {
  if (!params) return ""
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item))
    } else {
      search.append(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}

/**
 * POST multipart form data (file uploads). Kept separate from `request` because
 * the browser must set its own multipart boundary — setting Content-Type here
 * would corrupt the body.
 */
export async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST", body: form })

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response))
  }

  return (await response.json()) as T
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, params } = options
  const url = `${API_BASE_URL}${path}${buildQuery(params)}`

  const response = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
