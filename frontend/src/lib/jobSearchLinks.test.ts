import { describe, expect, it } from "vitest"
import { buildKeywords, buildSearchLinks, type SearchContext } from "./jobSearchLinks"

const base: SearchContext = {
  family: "all",
  location: "",
  roleType: "full_time",
  search: "",
}

function urlFor(site: string, context: SearchContext) {
  const link = buildSearchLinks(context).find((l) => l.site === site)
  if (!link) throw new Error(`no link for ${site}`)
  return new URL(link.url)
}

describe("buildKeywords", () => {
  it("uses the words a posting would actually contain, not our enum names", () => {
    expect(buildKeywords({ ...base, family: "policy_research" })).toBe(
      "economic policy research",
    )
    expect(buildKeywords({ ...base, family: "data_analytics" })).toBe("data analyst")
  })

  it("falls back to a broad term when no family is chosen", () => {
    expect(buildKeywords(base)).toBe("economics")
  })

  it("prefers what the user typed over the family default", () => {
    expect(buildKeywords({ ...base, family: "finance", search: "equity research" })).toBe(
      "equity research",
    )
  })

  it("appends intern in internship mode", () => {
    expect(buildKeywords({ ...base, family: "consulting", roleType: "internship" })).toBe(
      "consulting analyst intern",
    )
  })

  it("does not append intern twice when the search already says it", () => {
    expect(
      buildKeywords({ ...base, roleType: "internship", search: "summer internship" }),
    ).toBe("summer internship")
  })
})

describe("buildSearchLinks", () => {
  it("fills keywords and location into LinkedIn and Indeed", () => {
    const context = { ...base, family: "finance" as const, location: "Boston, MA" }

    const linkedIn = urlFor("LinkedIn", context)
    expect(linkedIn.origin + linkedIn.pathname).toBe(
      "https://www.linkedin.com/jobs/search/",
    )
    expect(linkedIn.searchParams.get("keywords")).toBe("finance analyst")
    expect(linkedIn.searchParams.get("location")).toBe("Boston, MA")

    const indeed = urlFor("Indeed", context)
    expect(indeed.searchParams.get("q")).toBe("finance analyst")
    expect(indeed.searchParams.get("l")).toBe("Boston, MA")
  })

  it("omits location entirely when the user has not given one", () => {
    expect(urlFor("LinkedIn", base).searchParams.has("location")).toBe(false)
    expect(urlFor("Indeed", base).searchParams.has("l")).toBe(false)
  })

  it("maps the mode toggle onto LinkedIn's experience filter", () => {
    expect(urlFor("LinkedIn", { ...base, roleType: "internship" }).searchParams.get("f_E")).toBe("1")
    expect(urlFor("LinkedIn", base).searchParams.get("f_E")).toBe("2")
  })

  it("marks Handshake as not pre-filled rather than inventing filter params", () => {
    const handshake = buildSearchLinks(base).find((l) => l.site === "Handshake")
    expect(handshake?.prefilled).toBe(false)
    expect(handshake?.url).toBe("https://app.joinhandshake.com/job-search")
  })
})
