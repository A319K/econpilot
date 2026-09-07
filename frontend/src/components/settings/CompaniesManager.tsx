import { useState } from "react"
import { ATS_TYPES, type AtsType } from "../../api/types"
import { useCompanies, useCreateCompany, useUpdateCompany } from "../../hooks/useCompanies"
import { Button } from "../ui/Button"
import { EmptyState } from "../ui/EmptyState"
import { useToast } from "../ui/Toast"

export function CompaniesManager() {
  const companiesQuery = useCompanies()
  const createCompany = useCreateCompany()
  const updateCompany = useUpdateCompany()
  const { push } = useToast()

  const [name, setName] = useState("")
  const [atsType, setAtsType] = useState<AtsType>("unknown")
  const [boardId, setBoardId] = useState("")

  function handleCreate() {
    if (!name.trim()) return
    createCompany.mutate(
      { name: name.trim(), ats_type: atsType, ats_board_id: boardId.trim() || null, is_target: true },
      {
        onSuccess: () => {
          setName("")
          setBoardId("")
          setAtsType("unknown")
        },
        onError: (error) => push({ tone: "error", message: `Could not add company: ${error.message}` }),
      },
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2 border-b border-(--color-border) pb-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">ats type</span>
          <select
            value={atsType}
            onChange={(e) => setAtsType(e.target.value as AtsType)}
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          >
            {ATS_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">board id</span>
          <input
            value={boardId}
            onChange={(e) => setBoardId(e.target.value)}
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          />
        </label>
        <Button variant="primary" onClick={handleCreate} disabled={createCompany.isPending || !name.trim()}>
          add target company
        </Button>
      </div>

      {companiesQuery.isLoading ? (
        <p className="text-(--color-fg-dim) text-xs">loading…</p>
      ) : (companiesQuery.data ?? []).length === 0 ? (
        <EmptyState title="No companies yet" hint="Add one above, or seed via scripts/seed_companies.py." />
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-(--color-fg-dim) border-b border-(--color-border) text-left">
              <th className="px-1 py-1.5 font-normal">name</th>
              <th className="px-1 py-1.5 font-normal">ats</th>
              <th className="px-1 py-1.5 font-normal">board id</th>
              <th className="px-1 py-1.5 font-normal">target</th>
            </tr>
          </thead>
          <tbody>
            {(companiesQuery.data ?? []).map((company) => (
              <tr key={company.id} className="border-b border-(--color-border-dim)">
                <td className="px-1 py-1.5 text-(--color-fg-bright)">{company.name}</td>
                <td className="text-(--color-fg-dim) px-1 py-1.5">{company.ats_type}</td>
                <td className="text-(--color-fg-dim) px-1 py-1.5">{company.ats_board_id ?? "—"}</td>
                <td className="px-1 py-1.5">
                  <button
                    onClick={() =>
                      updateCompany.mutate({ id: company.id, payload: { is_target: !company.is_target } })
                    }
                    className={company.is_target ? "text-(--color-accent)" : "text-(--color-fg-faint)"}
                    aria-label={`toggle target for ${company.name}`}
                  >
                    ★
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
