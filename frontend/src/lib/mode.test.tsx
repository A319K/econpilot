import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { useMode } from "./mode"

function ModeHarness() {
  const [mode, setMode] = useMode()
  return (
    <div>
      <p data-testid="mode-value">{mode}</p>
      <button onClick={() => setMode("full_time")}>switch to full-time</button>
      <button onClick={() => setMode("internship")}>switch to internship</button>
    </div>
  )
}

describe("useMode", () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it("defaults to internship when there is no URL param or stored value", () => {
    render(
      <MemoryRouter initialEntries={["/queue"]}>
        <ModeHarness />
      </MemoryRouter>,
    )

    expect(screen.getByTestId("mode-value")).toHaveTextContent("internship")
  })

  it("reads the mode from the ?mode= URL param when present", () => {
    render(
      <MemoryRouter initialEntries={["/queue?mode=full_time"]}>
        <ModeHarness />
      </MemoryRouter>,
    )

    expect(screen.getByTestId("mode-value")).toHaveTextContent("full_time")
  })

  it("the URL param wins over a stale localStorage value", () => {
    window.localStorage.setItem("econpilot.mode", "full_time")

    render(
      <MemoryRouter initialEntries={["/queue?mode=internship"]}>
        <ModeHarness />
      </MemoryRouter>,
    )

    expect(screen.getByTestId("mode-value")).toHaveTextContent("internship")
  })

  it("falls back to a stored mode when the URL has none", () => {
    window.localStorage.setItem("econpilot.mode", "full_time")

    render(
      <MemoryRouter initialEntries={["/queue"]}>
        <ModeHarness />
      </MemoryRouter>,
    )

    expect(screen.getByTestId("mode-value")).toHaveTextContent("full_time")
  })

  it("switching mode updates both localStorage and the rendered value", async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={["/queue"]}>
        <ModeHarness />
      </MemoryRouter>,
    )

    await user.click(screen.getByText("switch to full-time"))

    expect(screen.getByTestId("mode-value")).toHaveTextContent("full_time")
    expect(window.localStorage.getItem("econpilot.mode")).toBe("full_time")
  })
})
