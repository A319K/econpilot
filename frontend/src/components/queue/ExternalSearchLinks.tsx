import type { JobFamily, RoleType } from "../../api/types"
import { buildSearchLinks } from "../../lib/jobSearchLinks"
import { useProfile } from "../../hooks/useProfile"

/**
 * Hands the current search off to the sites students already use.
 *
 * EconPilot only sees employers whose job boards it can read. LinkedIn, Indeed
 * and Handshake cover the rest, and the student is already signed in to them —
 * so the useful thing we can do is build the query and open it for them.
 */
export function ExternalSearchLinks({
  family,
  location,
  roleType,
  search,
}: {
  family: JobFamily | "all"
  location: string
  roleType: RoleType
  search: string
}) {
  const profile = useProfile()

  // An empty location box falls back to where the user says they live, which is
  // a far better default than searching the entire country.
  const personal = profile.data?.personal
  const homeCity = personal?.city
    ? [personal.city, personal.state].filter(Boolean).join(", ")
    : ""
  const effectiveLocation = location.trim() || homeCity

  const links = buildSearchLinks({ family, location: effectiveLocation, roleType, search })

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-(--color-border) px-3 py-1.5 text-xs">
      <span className="text-(--color-fg-dim)">
        also search{effectiveLocation ? ` ${effectiveLocation}` : ""} on
      </span>
      {links.map((link) => (
        <a
          key={link.site}
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          title={link.hint}
          className="border border-(--color-border) px-1.5 py-0.5 text-(--color-fg-dim) hover:border-(--color-accent) hover:text-(--color-accent)"
        >
          {link.site}
          {!link.prefilled && <span className="text-(--color-fg-faint)"> ↗</span>}
        </a>
      ))}
      <span className="text-(--color-fg-faint)">
        opens in a new tab with your search filled in
      </span>
    </div>
  )
}
