import { NavLink } from "react-router-dom"
import { useWatcherStatus } from "../../hooks/useWatcher"
import { useMode } from "../../lib/mode"
import { BootHeader } from "./BootHeader"
import { ModeToggle } from "./ModeToggle"

const NAV_ITEMS = [
  { to: "/queue", label: "QUEUE" },
  { to: "/pipeline", label: "PIPELINE" },
  { to: "/stats", label: "STATS" },
  { to: "/settings", label: "SETTINGS" },
]

function watcherHeartbeatColor(status: ReturnType<typeof useWatcherStatus>["data"]): string {
  if (!status?.enabled) return "bg-(--color-fg-faint)"
  if (status.last_cycle && status.last_cycle.errors.length > 0) return "bg-(--color-status-queued)"
  return "bg-(--color-accent)"
}

function WatcherHeartbeat() {
  const { data } = useWatcherStatus()
  const enabled = data?.enabled ?? false
  const hasErrors = Boolean(data?.last_cycle?.errors.length)

  const label = !enabled ? "watcher disabled" : hasErrors ? "watcher: last cycle had errors" : "watcher enabled"

  return (
    <span className="inline-flex items-center gap-1.5 text-xs" title={label} aria-label={label}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${watcherHeartbeatColor(data)}`} />
      <span className="text-(--color-fg-dim)">watcher</span>
    </span>
  )
}

export function Rail({ onHelp }: { onHelp: () => void }) {
  const [mode, setMode] = useMode()

  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-(--color-border) bg-(--color-bg-panel)">
      <BootHeader />

      <div className="p-3">
        <ModeToggle mode={mode} onChange={setMode} />
      </div>

      <nav className="flex flex-col gap-0.5 px-3" aria-label="Main">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={{ pathname: item.to, search: `?mode=${mode}` }}
            className={({ isActive }) =>
              `border-l-2 px-2 py-1.5 text-xs font-medium tracking-wide transition-colors ${
                isActive
                  ? "border-(--color-accent) text-(--color-accent) bg-(--color-accent-bg)"
                  : "text-(--color-fg-dim) hover:text-(--color-fg-bright) border-transparent"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2 p-3">
        <WatcherHeartbeat />
        <button
          onClick={onHelp}
          className="text-(--color-fg-dim) hover:text-(--color-fg-bright) w-full border border-(--color-border) px-2 py-1.5 text-left text-xs"
        >
          <span className="text-(--color-accent)">[?]</span> help
        </button>
      </div>
    </aside>
  )
}
