import type { JobFamily, RoleType } from "../api/types"

/**
 * Pre-filled search links out to the sites students already use.
 *
 * None of LinkedIn, Indeed or Handshake exposes a job-search API we may call,
 * and scraping them breaches their terms and gets the user's own IP blocked —
 * EconPilot runs on the student's laptop, so they would eat that block. What we
 * can do is build the query for them and hand off: they land on a site they
 * already trust, already signed in, with the search filled in.
 */

export interface SearchContext {
  /** The queue's job-family dropdown; "all" when unset. */
  family: JobFamily | "all"
  /** The queue's location box, or the user's city from their profile. */
  location: string
  /** The internship / full_time mode toggle. */
  roleType: RoleType
  /** Free text from the queue's search box, if any. */
  search: string
}

export interface SearchLink {
  site: "LinkedIn" | "Indeed" | "Handshake"
  url: string
  /** Whether the site accepted our filters, or we could only link to its search page. */
  prefilled: boolean
  /** Shown on hover; explains an unfilled link rather than leaving it mysterious. */
  hint: string
}

/**
 * Search words per family. Deliberately the phrases a posting would use, not our
 * enum names — "policy_research" finds nothing on LinkedIn.
 */
const FAMILY_KEYWORDS: Record<JobFamily, string> = {
  finance: "finance analyst",
  consulting: "consulting analyst",
  data_analytics: "data analyst",
  corporate: "business analyst",
  policy_research: "economic policy research",
  other: "economics",
}

export function buildKeywords({ family, roleType, search }: SearchContext): string {
  const base = search.trim() || (family === "all" ? "economics" : FAMILY_KEYWORDS[family])
  // "intern" narrows hard on every one of these sites, and the mode toggle is
  // the user's clearest statement of what they want.
  if (roleType === "internship" && !/\bintern(ship)?\b/i.test(base)) {
    return `${base} intern`
  }
  return base
}

export function buildSearchLinks(context: SearchContext): SearchLink[] {
  const keywords = buildKeywords(context)
  const location = context.location.trim()

  const linkedIn = new URLSearchParams({ keywords })
  if (location) linkedIn.set("location", location)
  // f_E is LinkedIn's experience-level filter: 1 = internship, 2 = entry level.
  linkedIn.set("f_E", context.roleType === "internship" ? "1" : "2")

  const indeed = new URLSearchParams({ q: keywords })
  if (location) indeed.set("l", location)
  // Two weeks, roughly matching our own scan_max_age_days default of 21.
  indeed.set("fromage", "14")

  return [
    {
      site: "LinkedIn",
      url: `https://www.linkedin.com/jobs/search/?${linkedIn.toString()}`,
      prefilled: true,
      hint: `Search LinkedIn for "${keywords}"${location ? ` in ${location}` : ""}`,
    },
    {
      site: "Indeed",
      url: `https://www.indeed.com/jobs?${indeed.toString()}`,
      prefilled: true,
      hint: `Search Indeed for "${keywords}"${location ? ` in ${location}` : ""}`,
    },
    {
      // Handshake is per-school and behind a login, and its filters are numeric
      // ids that differ between schools — there is no link we can build that
      // would filter correctly for everyone. So this opens its search page and
      // the student types the search themselves.
      site: "Handshake",
      url: "https://app.joinhandshake.com/job-search",
      prefilled: false,
      hint: "Opens Handshake's job search — your school's Handshake can't be filtered from a link, so you'll type the search there",
    },
  ]
}
