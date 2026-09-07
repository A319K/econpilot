import { FunnelPanel } from "../components/stats/FunnelPanel"
import { StatusBars } from "../components/stats/StatusBars"
import { SubmissionTrend } from "../components/stats/SubmissionTrend"
import { TopCompaniesTable } from "../components/stats/TopCompaniesTable"
import { EmptyState } from "../components/ui/EmptyState"
import { Panel } from "../components/ui/Panel"
import { useStats } from "../hooks/useStats"
import { formatHours } from "../lib/format"
import { useMode } from "../lib/mode"

export function StatsPage() {
  const [mode] = useMode()
  const statsQuery = useStats()

  if (statsQuery.isLoading) {
    return <p className="text-(--color-fg-dim) p-4 text-xs">loading…</p>
  }
  if (statsQuery.isError || !statsQuery.data) {
    return <EmptyState title="Could not load stats" hint={statsQuery.error?.message} />
  }

  const stats = statsQuery.data[mode]
  const totalApplications = Object.values(stats.counts_by_status).reduce((a, b) => a + b, 0)

  if (totalApplications === 0) {
    return (
      <EmptyState
        title="No data yet"
        hint='Queue and submit some applications to see numbers here. Start on the Queue view.'
      />
    )
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      <header className="px-1 py-1">
        <h1 className="text-(--color-fg-bright) text-sm font-bold tracking-wide">STATS</h1>
      </header>

      <div className="grid grid-cols-2 gap-3">
        <Panel title="STATUS COUNTS">
          <StatusBars counts={stats.counts_by_status} />
        </Panel>

        <Panel title="SUBMITTED / LAST 30D">
          <SubmissionTrend data={stats.submitted_per_day} />
        </Panel>

        <Panel title="FUNNEL">
          <FunnelPanel funnel={stats.funnel} />
        </Panel>

        <Panel title="TOP COMPANIES">
          <TopCompaniesTable companies={stats.top_companies} />
        </Panel>
      </div>

      <Panel title="AVG TIME TO SUBMIT">
        <p className="text-(--color-accent) glow-text text-2xl font-bold tabular-nums">
          {formatHours(stats.avg_hours_to_submit)}
        </p>
        <p className="text-(--color-fg-dim) text-xs">from discovery to submission</p>
      </Panel>
    </div>
  )
}
