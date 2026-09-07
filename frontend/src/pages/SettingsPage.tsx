import { AnswerBankManager } from "../components/settings/AnswerBankManager"
import { CompaniesManager } from "../components/settings/CompaniesManager"
import { ResumeLibrary } from "../components/settings/ResumeLibrary"
import { WatcherPanel } from "../components/settings/WatcherPanel"
import { Panel } from "../components/ui/Panel"

export function SettingsPage() {
  return (
    <div className="flex flex-col gap-3 p-3">
      <header className="px-1 py-1">
        <h1 className="text-(--color-fg-bright) text-sm font-bold tracking-wide">SETTINGS</h1>
      </header>

      <Panel title="WATCHER">
        <WatcherPanel />
      </Panel>

      <Panel title="TARGET COMPANIES">
        <CompaniesManager />
      </Panel>

      <Panel title="RESUME LIBRARY">
        <ResumeLibrary />
      </Panel>

      <Panel title="ANSWER BANK">
        <AnswerBankManager />
      </Panel>
    </div>
  )
}
