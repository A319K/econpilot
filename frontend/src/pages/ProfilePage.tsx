import { useEffect, useMemo, useState } from "react"
import { ApiError } from "../api/client"
import type {
  Profile,
  ProfileEducation,
  ProfileProject,
  ProfileWorkExperience,
  ProfileWrite,
} from "../api/types"
import {
  CheckboxField,
  LinesField,
  MonthField,
  SelectField,
  TextField,
} from "../components/profile/fields"
import { RepeatableList } from "../components/profile/RepeatableList"
import { Button } from "../components/ui/Button"
import { Panel } from "../components/ui/Panel"
import { useToast } from "../components/ui/Toast"
import { useProfile, useSaveProfile } from "../hooks/useProfile"

const EEO_OPTIONS = [
  { value: "decline", label: "prefer not to say" },
  { value: "yes", label: "yes" },
  { value: "no", label: "no" },
] as const

/**
 * What the backend *might* send: every section optional, because an older or
 * partially-migrated backend is a real possibility on someone else's laptop.
 */
type LooseProfile = {
  [K in keyof ProfileWrite]?: Partial<ProfileWrite[K]>
}

/**
 * Strip the read-only flag and backfill anything the response didn't include.
 *
 * The form indexes deeply (`draft.eeo_defaults.veteran`), so one absent section
 * would otherwise throw and leave the user staring at a blank page — the worst
 * failure mode for people who can't open a console to find out why.
 * Normalising here keeps the page rendering against a partial response.
 */
function toWrite(profile: Profile): ProfileWrite {
  const { is_placeholder: _ignored, ...rest } = profile
  const loose = rest as LooseProfile

  return {
    personal: {
      name: "",
      email: "",
      phone: "",
      city: "",
      state: "",
      address: null,
      zip: null,
      country: null,
      linkedin: null,
      github: null,
      website: null,
      ...loose.personal,
    },
    education: rest.education ?? [],
    work_experience: rest.work_experience ?? [],
    projects: rest.projects ?? [],
    skills: { languages: [], frameworks: [], tools: [], ...loose.skills },
    eeo_defaults: {
      gender: null,
      ethnicity: null,
      veteran: null,
      disability: null,
      ...loose.eeo_defaults,
    },
    standard_answers: {
      work_authorization: "",
      requires_sponsorship: false,
      willing_to_relocate: true,
      graduation_date: "",
      ...loose.standard_answers,
    },
  }
}

function trimLines(lines: string[]): string[] {
  return lines.map((l) => l.trim()).filter(Boolean)
}

/** Drop blank bullets/skills so a stray empty line never reaches the file. */
function clean(draft: ProfileWrite): ProfileWrite {
  return {
    ...draft,
    work_experience: draft.work_experience.map((w) => ({ ...w, bullets: trimLines(w.bullets ?? []) })),
    projects: draft.projects.map((p) => ({ ...p, bullets: trimLines(p.bullets ?? []) })),
    skills: {
      languages: trimLines(draft.skills.languages),
      frameworks: trimLines(draft.skills.frameworks),
      tools: trimLines(draft.skills.tools),
    },
  }
}

type Errors = Record<string, string>

/**
 * Validate in the browser so mistakes surface next to the field instead of as
 * a server error the reader can't parse. The backend still validates on PUT —
 * this is the friendly first pass, not the security boundary.
 */
function validate(draft: ProfileWrite): Errors {
  const errors: Errors = {}
  const p = draft.personal

  if (!p.name.trim()) errors["personal.name"] = "required"
  if (!p.email.trim()) errors["personal.email"] = "required"
  else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(p.email.trim()))
    errors["personal.email"] = "that doesn't look like an email address"
  if (!p.phone.trim()) errors["personal.phone"] = "required"
  if (!p.city.trim()) errors["personal.city"] = "required"
  if (!p.state.trim()) errors["personal.state"] = "required"

  draft.education.forEach((e, i) => {
    if (!e.school.trim()) errors[`education.${i}.school`] = "required"
    if (!e.major.trim()) errors[`education.${i}.major`] = "required"
    if (e.gpa !== null && (e.gpa < 0 || e.gpa > 5))
      errors[`education.${i}.gpa`] = "must be between 0 and 5"
  })

  draft.work_experience.forEach((w, i) => {
    if (!w.company.trim()) errors[`work.${i}.company`] = "required"
    if (!w.title.trim()) errors[`work.${i}.title`] = "required"
  })

  draft.projects.forEach((pr, i) => {
    if (!pr.name.trim()) errors[`project.${i}.name`] = "required"
  })

  if (!draft.standard_answers.work_authorization.trim())
    errors["answers.work_authorization"] = "required"

  return errors
}

export function ProfilePage() {
  const profileQuery = useProfile()
  const saveProfile = useSaveProfile()
  const toast = useToast()

  const [draft, setDraft] = useState<ProfileWrite | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const loaded = profileQuery.data

  // Seed the form once the profile arrives. Re-seeds only when the server's
  // version changes, so typing is never interrupted by a refetch.
  useEffect(() => {
    if (loaded) setDraft(toWrite(loaded))
  }, [loaded])

  const dirty = useMemo(() => {
    if (!draft || !loaded) return false
    return JSON.stringify(draft) !== JSON.stringify(toWrite(loaded))
  }, [draft, loaded])

  // Warn before losing unsaved edits to a tab close or reload.
  useEffect(() => {
    if (!dirty) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener("beforeunload", onBeforeUnload)
    return () => window.removeEventListener("beforeunload", onBeforeUnload)
  }, [dirty])

  if (profileQuery.isLoading) {
    return <p className="text-(--color-fg-dim) p-3 text-xs">loading your profile…</p>
  }

  if (profileQuery.isError || !draft) {
    return (
      <div className="flex flex-col gap-2 p-3">
        <p className="text-(--color-status-rejected) text-xs">
          Couldn't load your profile. Is the backend running on port 8000?
        </p>
        <div>
          <Button onClick={() => void profileQuery.refetch()}>try again</Button>
        </div>
      </div>
    )
  }

  const set = (patch: Partial<ProfileWrite>) => setDraft({ ...draft, ...patch })

  const handleSave = () => {
    const cleaned = clean(draft)
    const found = validate(cleaned)
    setErrors(found)
    if (Object.keys(found).length > 0) {
      toast.push({ tone: "error", message: "Some fields need fixing — see the red notes below." })
      return
    }
    setDraft(cleaned)
    saveProfile.mutate(cleaned, {
      onSuccess: () => toast.push({ tone: "success", message: "Profile saved." }),
      onError: (err) =>
        toast.push({
          tone: "error",
          message:
            err instanceof ApiError
              ? `Couldn't save: ${err.detail}`
              : "Couldn't save your profile. Is the backend still running?",
        }),
    })
  }

  const handleReset = () => {
    if (loaded) setDraft(toWrite(loaded))
    setErrors({})
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      <header className="flex flex-wrap items-center justify-between gap-2 px-1 py-1">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-(--color-fg-bright) text-sm font-bold tracking-wide">PROFILE</h1>
          <p className="text-(--color-fg-dim) text-xs">
            Your details, used to fill in applications and write your materials.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dirty ? <span className="text-(--color-fg-dim) text-xs">unsaved changes</span> : null}
          <Button onClick={handleReset} disabled={!dirty || saveProfile.isPending}>
            undo changes
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={saveProfile.isPending}>
            {saveProfile.isPending ? "saving…" : "save profile"}
          </Button>
        </div>
      </header>

      {loaded?.is_placeholder ? (
        <div className="border border-(--color-status-queued) px-3 py-2 text-xs">
          <p className="text-(--color-fg-bright) font-bold">This is example data, not you yet.</p>
          <p className="text-(--color-fg-dim) mt-1">
            Replace it with your own details and hit <strong>save profile</strong>. Until you do,
            anything EconPilot writes for you will use the example name.
          </p>
        </div>
      ) : null}

      <Panel title="ABOUT YOU">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <TextField
            label="Full name"
            value={draft.personal.name}
            error={errors["personal.name"]}
            onChange={(v) => set({ personal: { ...draft.personal, name: v } })}
          />
          <TextField
            label="Email"
            type="email"
            value={draft.personal.email}
            error={errors["personal.email"]}
            onChange={(v) => set({ personal: { ...draft.personal, email: v } })}
          />
          <TextField
            label="Phone"
            type="tel"
            value={draft.personal.phone}
            error={errors["personal.phone"]}
            onChange={(v) => set({ personal: { ...draft.personal, phone: v } })}
          />
          <TextField
            label="Street address"
            value={draft.personal.address ?? ""}
            hint="optional"
            onChange={(v) => set({ personal: { ...draft.personal, address: v || null } })}
          />
          <TextField
            label="City"
            value={draft.personal.city}
            error={errors["personal.city"]}
            onChange={(v) => set({ personal: { ...draft.personal, city: v } })}
          />
          <TextField
            label="State"
            value={draft.personal.state}
            error={errors["personal.state"]}
            onChange={(v) => set({ personal: { ...draft.personal, state: v } })}
          />
          <TextField
            label="ZIP code"
            value={draft.personal.zip ?? ""}
            hint="optional"
            onChange={(v) => set({ personal: { ...draft.personal, zip: v || null } })}
          />
          <TextField
            label="Country"
            value={draft.personal.country ?? ""}
            hint="optional"
            onChange={(v) => set({ personal: { ...draft.personal, country: v || null } })}
          />
          <TextField
            label="LinkedIn"
            type="url"
            value={draft.personal.linkedin ?? ""}
            hint="optional — the full link"
            onChange={(v) => set({ personal: { ...draft.personal, linkedin: v || null } })}
          />
          <TextField
            label="GitHub"
            type="url"
            value={draft.personal.github ?? ""}
            hint="optional"
            onChange={(v) => set({ personal: { ...draft.personal, github: v || null } })}
          />
          <TextField
            label="Personal website"
            type="url"
            value={draft.personal.website ?? ""}
            hint="optional"
            onChange={(v) => set({ personal: { ...draft.personal, website: v || null } })}
          />
        </div>
      </Panel>

      <Panel title="EDUCATION">
        <RepeatableList<ProfileEducation>
          items={draft.education}
          onChange={(education) => set({ education })}
          makeEmpty={() => ({
            school: "",
            degree: "B.A.",
            major: "Economics",
            gpa: null,
            start: "",
            end: "",
          })}
          titleOf={(e) => [e.school, e.major].filter(Boolean).join(" — ")}
          addLabel="add a school"
          emptyLabel="No schools yet — add the one you're attending."
        >
          {(item, update, i) => (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <TextField
                label="School"
                value={item.school}
                error={errors[`education.${i}.school`]}
                onChange={(v) => update({ school: v })}
              />
              <TextField
                label="Degree"
                value={item.degree}
                hint="e.g. B.A., B.S."
                onChange={(v) => update({ degree: v })}
              />
              <TextField
                label="Major"
                value={item.major}
                error={errors[`education.${i}.major`]}
                onChange={(v) => update({ major: v })}
              />
              <TextField
                label="GPA"
                value={item.gpa === null ? "" : String(item.gpa)}
                hint="optional — leave blank to hide it"
                error={errors[`education.${i}.gpa`]}
                onChange={(v) => {
                  const n = Number(v)
                  update({ gpa: v.trim() === "" || Number.isNaN(n) ? null : n })
                }}
              />
              <MonthField label="Started" value={item.start} onChange={(v) => update({ start: v })} />
              <MonthField
                label="Finished (or expected)"
                value={item.end}
                onChange={(v) => update({ end: v })}
              />
            </div>
          )}
        </RepeatableList>
      </Panel>

      <Panel title="WORK EXPERIENCE">
        <RepeatableList<ProfileWorkExperience>
          items={draft.work_experience}
          onChange={(work_experience) => set({ work_experience })}
          makeEmpty={() => ({ company: "", title: "", start: "", end: "", bullets: [] })}
          titleOf={(w) => [w.company, w.title].filter(Boolean).join(" — ")}
          addLabel="add a job"
          emptyLabel="Nothing here yet. Add internships, part-time jobs, campus roles — all of it counts."
        >
          {(item, update, i) => (
            <div className="flex flex-col gap-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <TextField
                  label="Company"
                  value={item.company}
                  error={errors[`work.${i}.company`]}
                  onChange={(v) => update({ company: v })}
                />
                <TextField
                  label="Job title"
                  value={item.title}
                  error={errors[`work.${i}.title`]}
                  onChange={(v) => update({ title: v })}
                />
                <MonthField label="Started" value={item.start} onChange={(v) => update({ start: v })} />
                <MonthField label="Ended" value={item.end} onChange={(v) => update({ end: v })} />
              </div>
              <LinesField
                label="What you did"
                value={item.bullets}
                hint="One bullet per line — these go straight onto your resume."
                onChange={(bullets) => update({ bullets })}
              />
            </div>
          )}
        </RepeatableList>
      </Panel>

      <Panel title="PROJECTS">
        <RepeatableList<ProfileProject>
          items={draft.projects}
          onChange={(projects) => set({ projects })}
          makeEmpty={() => ({ name: "", description: null, bullets: [], url: null })}
          titleOf={(p) => p.name}
          addLabel="add a project"
          emptyLabel="Optional — coursework, research, or anything you built."
        >
          {(item, update, i) => (
            <div className="flex flex-col gap-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField
                  label="Project name"
                  value={item.name}
                  error={errors[`project.${i}.name`]}
                  onChange={(v) => update({ name: v })}
                />
                <TextField
                  label="Link"
                  type="url"
                  value={item.url ?? ""}
                  hint="optional"
                  onChange={(v) => update({ url: v || null })}
                />
              </div>
              <TextField
                label="One-line description"
                value={item.description ?? ""}
                hint="optional"
                onChange={(v) => update({ description: v || null })}
              />
              <LinesField
                label="Details"
                value={item.bullets}
                onChange={(bullets) => update({ bullets })}
              />
            </div>
          )}
        </RepeatableList>
      </Panel>

      <Panel title="SKILLS">
        <div className="grid gap-3 lg:grid-cols-3">
          <LinesField
            label="Software & tools"
            value={draft.skills.tools}
            hint="one per line — e.g. Excel, Bloomberg, Tableau"
            onChange={(tools) => set({ skills: { ...draft.skills, tools } })}
          />
          <LinesField
            label="Languages & technical"
            value={draft.skills.languages}
            hint="one per line — e.g. Python, R, Stata, SQL"
            onChange={(languages) => set({ skills: { ...draft.skills, languages } })}
          />
          <LinesField
            label="Methods & frameworks"
            value={draft.skills.frameworks}
            hint="one per line — e.g. Econometrics, Financial modeling"
            onChange={(frameworks) => set({ skills: { ...draft.skills, frameworks } })}
          />
        </div>
      </Panel>

      <Panel title="APPLICATION ANSWERS">
        <p className="text-(--color-fg-dim) mb-3 text-xs">
          The questions almost every application asks. Filling these in once lets EconPilot answer
          them for you.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <TextField
            label="Work authorization"
            value={draft.standard_answers.work_authorization}
            error={errors["answers.work_authorization"]}
            hint="e.g. U.S. Citizen, Permanent Resident, F-1 student"
            onChange={(v) =>
              set({ standard_answers: { ...draft.standard_answers, work_authorization: v } })
            }
          />
          <MonthField
            label="Graduation date"
            value={draft.standard_answers.graduation_date}
            onChange={(v) =>
              set({ standard_answers: { ...draft.standard_answers, graduation_date: v } })
            }
          />
          <div className="flex flex-col justify-center gap-2">
            <CheckboxField
              label="I'll need visa sponsorship"
              value={draft.standard_answers.requires_sponsorship}
              onChange={(v) =>
                set({ standard_answers: { ...draft.standard_answers, requires_sponsorship: v } })
              }
            />
            <CheckboxField
              label="I'm willing to relocate"
              value={draft.standard_answers.willing_to_relocate}
              onChange={(v) =>
                set({ standard_answers: { ...draft.standard_answers, willing_to_relocate: v } })
              }
            />
          </div>
        </div>
      </Panel>

      <Panel title="DEMOGRAPHIC QUESTIONS">
        <p className="text-(--color-fg-dim) mb-3 text-xs">
          Employers ask these separately and they never affect hiring decisions. "Prefer not to say"
          is always a valid answer — it's the default here.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SelectField
            label="Veteran status"
            value={draft.eeo_defaults.veteran ?? "decline"}
            options={EEO_OPTIONS}
            onChange={(v) => set({ eeo_defaults: { ...draft.eeo_defaults, veteran: v } })}
          />
          <SelectField
            label="Disability status"
            value={draft.eeo_defaults.disability ?? "decline"}
            options={EEO_OPTIONS}
            onChange={(v) => set({ eeo_defaults: { ...draft.eeo_defaults, disability: v } })}
          />
          <TextField
            label="Gender"
            value={draft.eeo_defaults.gender ?? ""}
            hint="or leave as decline"
            onChange={(v) => set({ eeo_defaults: { ...draft.eeo_defaults, gender: v || null } })}
          />
          <TextField
            label="Race / ethnicity"
            value={draft.eeo_defaults.ethnicity ?? ""}
            hint="or leave as decline"
            onChange={(v) => set({ eeo_defaults: { ...draft.eeo_defaults, ethnicity: v || null } })}
          />
        </div>
      </Panel>
    </div>
  )
}
