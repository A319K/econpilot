import { useHealth } from "../../hooks/useHealth"

const APP_NAME = "ECONPILOT"
const APP_VERSION = "v0.4.0"

export function BootHeader() {
  const { data, isError, isLoading } = useHealth()
  const connected = !isLoading && !isError && data?.status === "ok" && data.db === "ok"

  const dotColor = isLoading
    ? "var(--color-fg-dim)"
    : connected
      ? "var(--color-accent)"
      : "var(--color-status-rejected)"

  return (
    <div className="border-b border-(--color-border) px-3 py-2.5 text-xs">
      <div className="flex items-center gap-1.5">
        <span className="text-(--color-fg-bright) glow-text font-bold tracking-widest">{APP_NAME}</span>
        <span className="bg-(--color-accent) inline-block h-3.5 w-[7px] cursor-blink" aria-hidden="true" />
      </div>
      <div className="text-(--color-fg-dim) mt-1 flex items-center justify-between">
        <span>{APP_VERSION}</span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: dotColor }}
            aria-hidden="true"
          />
          <span>{isLoading ? "connecting" : connected ? "online" : "offline"}</span>
        </span>
      </div>
    </div>
  )
}
