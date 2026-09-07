import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useRef, useState } from "react"
import { describe, expect, it, vi } from "vitest"
import { useListKeyboardNav } from "./useListKeyboardNav"

interface Item {
  id: number
  name: string
}

const ITEMS: Item[] = [
  { id: 1, name: "alpha" },
  { id: 2, name: "beta" },
  { id: 3, name: "gamma" },
]

function Harness({ onOpen, onQueue }: { onOpen: (item: Item) => void; onQueue: (item: Item) => void }) {
  const [selectedId, setSelectedId] = useState<number | null>(ITEMS[0].id)
  const searchRef = useRef<HTMLInputElement>(null)

  useListKeyboardNav({ items: ITEMS, selectedId, onSelect: setSelectedId, onOpen, onQueue, searchInputRef: searchRef })

  return (
    <div>
      <p data-testid="selected">{ITEMS.find((i) => i.id === selectedId)?.name}</p>
      <input ref={searchRef} data-testid="search" placeholder="search" />
    </div>
  )
}

describe("useListKeyboardNav", () => {
  it("j moves selection to the next item", async () => {
    const user = userEvent.setup()
    render(<Harness onOpen={vi.fn()} onQueue={vi.fn()} />)

    expect(screen.getByTestId("selected")).toHaveTextContent("alpha")
    await user.keyboard("j")
    expect(screen.getByTestId("selected")).toHaveTextContent("beta")
    await user.keyboard("j")
    expect(screen.getByTestId("selected")).toHaveTextContent("gamma")
  })

  it("j stops at the last item instead of wrapping", async () => {
    const user = userEvent.setup()
    render(<Harness onOpen={vi.fn()} onQueue={vi.fn()} />)

    await user.keyboard("jjjj")
    expect(screen.getByTestId("selected")).toHaveTextContent("gamma")
  })

  it("k moves selection to the previous item and stops at the first", async () => {
    const user = userEvent.setup()
    render(<Harness onOpen={vi.fn()} onQueue={vi.fn()} />)

    await user.keyboard("jj")
    expect(screen.getByTestId("selected")).toHaveTextContent("gamma")
    await user.keyboard("kkkk")
    expect(screen.getByTestId("selected")).toHaveTextContent("alpha")
  })

  it("Enter calls onOpen with the currently selected item", async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<Harness onOpen={onOpen} onQueue={vi.fn()} />)

    await user.keyboard("j")
    await user.keyboard("{Enter}")

    expect(onOpen).toHaveBeenCalledWith(ITEMS[1])
  })

  it("q calls onQueue with the currently selected item", async () => {
    const user = userEvent.setup()
    const onQueue = vi.fn()
    render(<Harness onOpen={vi.fn()} onQueue={onQueue} />)

    await user.keyboard("q")

    expect(onQueue).toHaveBeenCalledWith(ITEMS[0])
  })

  it("/ focuses the search input and prevents typing '/' into it", async () => {
    const user = userEvent.setup()
    render(<Harness onOpen={vi.fn()} onQueue={vi.fn()} />)

    const search = screen.getByTestId("search")
    expect(search).not.toHaveFocus()

    await user.keyboard("/")

    expect(search).toHaveFocus()
  })

  it("does not navigate rows while typing in the search input", async () => {
    const user = userEvent.setup()
    const onQueue = vi.fn()
    render(<Harness onOpen={vi.fn()} onQueue={onQueue} />)

    const search = screen.getByTestId("search")
    await user.click(search)
    await user.keyboard("q")

    expect(onQueue).not.toHaveBeenCalled()
    expect(search).toHaveValue("q")
  })

  it("Escape blurs the search input", async () => {
    const user = userEvent.setup()
    render(<Harness onOpen={vi.fn()} onQueue={vi.fn()} />)

    const search = screen.getByTestId("search")
    await user.click(search)
    expect(search).toHaveFocus()

    await user.keyboard("{Escape}")
    expect(search).not.toHaveFocus()
  })
})
