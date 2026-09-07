import type { CompanyCount } from "../../api/types"

export function TopCompaniesTable({ companies }: { companies: CompanyCount[] }) {
  if (companies.length === 0) {
    return <p className="text-(--color-fg-dim) text-xs">no applications yet</p>
  }

  const max = Math.max(1, ...companies.map((c) => c.count))

  return (
    <table className="w-full text-xs">
      <tbody>
        {companies.map((company, i) => (
          <tr key={company.company_id}>
            <td className="text-(--color-fg-faint) w-5 py-1 tabular-nums">{i + 1}</td>
            <td className="text-(--color-fg) py-1">{company.company_name}</td>
            <td className="w-32 py-1">
              <div className="h-2 bg-(--color-bg-inset)">
                <div
                  className="bg-(--color-accent) h-full"
                  style={{ width: `${(company.count / max) * 100}%` }}
                />
              </div>
            </td>
            <td className="text-(--color-fg-bright) w-6 py-1 text-right tabular-nums">{company.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
