import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "../api/client"
import { ToastProvider } from "../components/ui/Toast"
import { PipelinePage } from "./PipelinePage"

vi.mock("../api/applications", () => ({
  applicationsApi: {
    list: vi.fn(),
    updateStatus: vi.fn(),
  },
}))

import { applicationsApi } from "../api/applications"

const QUEUED_APP = {
  id: 42,
  job_id: 7,
  status: "queued" as const,
  resume_version_id: null,
  cover_letter_id: null,
  submitted_at: null,
  notes: null,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
  job: {
    id: 7,
    title: "Backend Intern",
    company_name: "Acme",
    url: "https://example.com/job/7",
    score: 80,
    role_type: "internship" as const,
  },
}

function makeDataTransfer() {
  const data = new Map<string, string>()
  return {
    setData: (type: string, value: string) => data.set(type, value),
    getData: (type: string) => data.get(type) ?? "",
    effectAllowed: "move",
  }
}

function renderPipeline() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/pipeline?mode=internship"]}>
          <PipelinePage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe("PipelinePage kanban drag", () => {
  beforeEach(() => {
    vi.mocked(applicationsApi.list).mockResolvedValue([QUEUED_APP])
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  it("snaps a card back to its original column and shows a toast when the server rejects the transition", async () => {
    vi.mocked(applicationsApi.updateStatus).mockRejectedValue(
      new ApiError(409, "Cannot transition from 'queued' to 'offer'"),
    )

    renderPipeline()

    const card = await screen.findByTestId("kanban-card-42")
    const offerColumn = screen.getByTestId("kanban-column-offer")
    const dataTransfer = makeDataTransfer()

    fireEvent.dragStart(card, { dataTransfer })
    fireEvent.dragOver(offerColumn, { dataTransfer })
    fireEvent.drop(offerColumn, { dataTransfer })

    // Toast explaining the invalid transition appears.
    await screen.findByText(/Cannot transition from 'queued' to 'offer'/)

    // Card snaps back to the queued column - never actually appears under offer.
    const queuedColumn = screen.getByTestId("kanban-column-queued")
    expect(within(queuedColumn).getByTestId("kanban-card-42")).toBeInTheDocument()
    expect(within(offerColumn).queryByTestId("kanban-card-42")).not.toBeInTheDocument()
  })

  it("force-retries and moves the card when the toast's force action is clicked", async () => {
    let currentStatus: string = "queued"
    vi.mocked(applicationsApi.list).mockImplementation(() =>
      Promise.resolve([{ ...QUEUED_APP, status: currentStatus as "queued" }]),
    )
    vi.mocked(applicationsApi.updateStatus).mockImplementation((_id, payload) => {
      if (!payload.force) {
        return Promise.reject(new ApiError(409, "Cannot transition from 'queued' to 'offer'"))
      }
      currentStatus = payload.status
      // Only .status/.id are read by the code under test (cache write in
      // onSettled); the rest of ApplicationDetail's shape isn't exercised.
      return Promise.resolve({
        ...QUEUED_APP,
        status: payload.status,
        status_history: [],
        resume_version: null,
        cover_letter: null,
      } as unknown as import("../api/types").ApplicationDetail)
    })

    renderPipeline()

    const card = await screen.findByTestId("kanban-card-42")
    const offerColumn = screen.getByTestId("kanban-column-offer")
    const dataTransfer = makeDataTransfer()

    fireEvent.dragStart(card, { dataTransfer })
    fireEvent.dragOver(offerColumn, { dataTransfer })
    fireEvent.drop(offerColumn, { dataTransfer })

    const forceButton = await screen.findByText("Force move anyway")
    fireEvent.click(forceButton)

    await waitFor(() => {
      expect(applicationsApi.updateStatus).toHaveBeenLastCalledWith(42, {
        status: "offer",
        force: true,
      })
    })

    await waitFor(() => {
      expect(within(offerColumn).getByTestId("kanban-card-42")).toBeInTheDocument()
    })
  })
})
