import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ApiError, request } from "./client"

describe("api client", () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it("builds the request URL with the configured base and no query string when params are absent", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await request("/jobs")

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]
    expect(url).toBe("http://localhost:8000/jobs")
  })

  it("serializes scalar query params", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response("[]", { status: 200 }))

    await request("/jobs", { params: { min_score: 50, is_active: true, source: undefined } })

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0] as [string]
    const parsed = new URL(url)
    expect(parsed.searchParams.get("min_score")).toBe("50")
    expect(parsed.searchParams.get("is_active")).toBe("true")
    expect(parsed.searchParams.has("source")).toBe(false)
  })

  it("repeats array query params instead of joining them", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response("[]", { status: 200 }))

    await request("/applications", { params: { status: ["queued", "submitted"] } })

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0] as [string]
    const parsed = new URL(url)
    expect(parsed.searchParams.getAll("status")).toEqual(["queued", "submitted"])
  })

  it("sends a JSON body and content-type header for mutating requests", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({ id: 1 }), { status: 201 }))

    await request("/jobs/manual", { method: "POST", body: { url: "https://x.com", role_type: "internship" } })

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe("POST")
    expect(init.headers).toEqual({ "Content-Type": "application/json" })
    expect(JSON.parse(init.body as string)).toEqual({ url: "https://x.com", role_type: "internship" })
  })

  it("returns undefined for a 204 No Content response", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(null, { status: 204 }))

    const result = await request("/applications/1")
    expect(result).toBeUndefined()
  })

  it("throws ApiError with the parsed detail message on a non-ok JSON response", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Application not found" }), { status: 404 }),
    )

    await expect(request("/applications/999")).rejects.toMatchObject({
      status: 404,
      detail: "Application not found",
    })
  })

  it("throws ApiError with status text when the error response isn't JSON", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response("plain text error", { status: 500, statusText: "Internal Server Error" }),
    )

    await expect(request("/stats")).rejects.toBeInstanceOf(ApiError)
  })

  it("surfaces the 409 status for invalid state transitions", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Cannot transition from 'discovered' to 'offer'" }), {
        status: 409,
      }),
    )

    try {
      await request("/applications/1/status", { method: "PATCH", body: { status: "offer" } })
      expect.unreachable("expected request to throw")
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(409)
      expect((error as ApiError).detail).toContain("Cannot transition")
    }
  })
})
