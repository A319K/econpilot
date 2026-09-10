# CLAUDE.md

Guidance for Claude Code when working in this repo. EconPilot is a **local-first**
job-application system: it discovers postings from company ATS APIs, tailors a
resume + cover letter per job with an LLM, tracks each application through a
validated pipeline, and drives a human-supervised browser agent that fills forms
and **stops at review so the user clicks submit**.

## ⚠️ Read this first — what EconPilot is and where it stands

EconPilot is a **fork of JobPilot** (`~/Documents/jobpilot`), taken as a clean
template. JobPilot targets **tech / software-engineering** roles. EconPilot's
purpose is to target **economics-degree roles instead** — finance, consulting,
economic consulting, data/analytics, corporate/rotational, policy & central
banking, and the academic pre-doc pipeline.

**The engine is role-agnostic and was carried over intact.** ATS discovery, the
normalize/dedup/score pipeline, LLM materials generation, the FastAPI+SQLite
backend, the React frontend, and the supervised browser agent all work the same
regardless of what kind of role is being searched. **What makes JobPilot
"tech" is config and data, not plumbing** — the company seed list, a
`discovery_tech_only` filter, tech-oriented title/keyword logic, scoring weights,
and some frontend copy.

So the work here is **re-targeting, not rewriting.** When you touch this repo,
assume the goal is econ/finance roles, and treat any remaining tech-specific
behavior as a thing to change, not a thing to preserve.

**The core re-targeting is done** (taxonomy, roster, scoring — see "Where things
stand" below). The open problem is no longer that EconPilot finds tech roles; it
is that it does not find *enough* roles, and that several shipped capabilities
are only reachable by someone willing to run a script and edit YAML.

## Who this is for — and why that constrains every design choice

**EconPilot is not being built for its author.** JobPilot was: a CS major running
his own tooling, happy to edit YAML and keep two terminals open. EconPilot is
being built **for Aiden's friends who are economics majors.** They use computers
fine — they are not beginners at *computers*. What they are not fluent in is
**developer vocabulary and developer workflow**: virtualenvs, terminals, YAML
syntax, API keys, ports, "run migrations", "clone the repo".

That single fact outranks feature work. A capability the user cannot reach
without asking Aiden for help does not count as shipped.

**The standing rules that follow from it:**

- **Configuration belongs in the UI, not in files.** Anything a user must
  personalize — their profile, their target companies, their resume, their API
  key — must be editable from a screen in the app. Editing `profile.yaml` or
  `companies.yaml` in a text editor is an *Aiden-only* path. The YAML files stay
  as the storage format and the seed/defaults mechanism; they stop being the
  interface.

  **The Profile page is the reference implementation of this pattern** (added
  2026-09-07): `GET`/`PUT /profile` read and atomically rewrite `profile.yaml`,
  `ProfilePage.tsx` renders it as a real form, and `is_placeholder` on the read
  response drives a banner telling the user the example data isn't them yet.
  Copy that shape — file stays the storage, screen becomes the interface, and
  the API reports when a config is still un-personalized — when moving
  `companies.yaml` or the LLM key into the app.
- **Every error message is user-facing copy.** Assume it will be read by someone
  who cannot interpret a stack trace and will not open a log file. Say what went
  wrong and what to do next, in plain language, in the UI.
- **The terminal is fine; the text editor is not.** Calibrated by Aiden
  2026-09-07: a friend can open Terminal, paste a command, and keep two windows
  running. What they should never have to do is open a code editor to hand-edit
  a config file. So README commands can be copy-pasteable blocks — but they must
  be *complete* (including installing the prerequisites) and pasteable without
  understanding them. Explain what a step is for, never what it means.
- **Nothing that requires a paid signup can gate the core loop.** Discovery,
  scoring, and tracking are deterministic and work with no LLM key — that path
  must stay fully usable and must be the default. Materials generation and the
  agent are the upgrade, clearly marked as needing a key.
- **Assume no LaTeX, no Chromium, no `tectonic`.** Anything requiring a heavy
  local toolchain must degrade gracefully to a working fallback, never to a
  crash or a blank screen.
- **Jargon in the interface is a bug.** "ATS", "scan", "pipeline", "seed" are
  internal words. User-visible copy uses the words an econ student would use.

### Distribution

The plan is **give them the repo**, not host it — decided 2026-09-07. Hosting is
a much larger change than it looks: it needs multi-user auth and data isolation
(none exists — the DB is single-user by construction), it would put their resumes
and contact details on someone else's server, and **the browser agent
fundamentally cannot be hosted** — it drives a headed browser on the user's own
desktop so they can watch it and click submit themselves.

So the target experience is a **local app that installs easily**, not a website.
`docker-compose.yml` already runs the API + dashboard as one command and is the
most promising base for this. Optimize toward: download → one step → a browser
tab opens → an in-app onboarding wizard collects everything else.

When adding anything to the setup path, ask: *could a friend do this alone, on a
laptop, without calling Aiden?* If not, it needs a different design.

### Scope decisions (settled — don't reopen without Aiden)

**Gmail auto-status tracking: out of scope.** Decided 2026-09-07. The idea was
to read replies from employers and advance application status automatically.
Rejected on accuracy, not effort: inferring "rejected" vs "interview" from email
text is right most of the time, and a single misread silently corrupts the
tracker the user is trusting. A quietly wrong pipeline is worse than a manual
one. If it ever returns, it must *propose* status changes for one-click
confirmation — never move an application on its own — matching the rule that
the browser agent stops before submit. Google OAuth is also badly
non-technical-hostile (each user creating a Cloud project and consent screen),
which would undo the setup work, and it is a separate blocker from accuracy.

**Per-job resume rewriting stays OFF.** `prepare_tailor_default` is `False` and
that is the intended design, not a placeholder: Prepare selects the best-fit
**pre-built base resume** (`backend/templates/resumes/`, keyed by `JobFamily`)
and reuses its compiled PDF. Aiden's model is *2-3 role-specific resumes*, not a
fresh one per application — regenerating every time produces inconsistent
formatting and burns tokens for no gain. Per-job tailoring stays reachable via
`tailor=true` on a single Prepare request. **When the econ pivot re-does
`JobFamily`, the resume templates must be re-cut along the new families too** —
they are keyed by it.

**So the LLM's real job here is cover letters and agent form answers**, not
resumes. That makes the spend small: Aiden can issue a dedicated OpenRouter key
with a `limit` (per-key credit cap, optionally daily-resetting — verified in
OpenRouter's provisioning docs 2026-09-07) and share that. It still goes in each
user's `backend/.env` and is **never committed** — the repo is public, and keys
in public repos get scraped and revoked.

### Known gap: base resumes are LaTeX

`backend/templates/resumes/*.tex` compile via `tectonic`. That is fine for
Aiden and wrong for the audience — an econ major has a résumé in Word or PDF and
will not write LaTeX or install a TeX engine. The natural fix is letting users
**upload 2-3 finished PDFs** and tag each with a role family, which matches the
pre-built-resume design exactly and drops LaTeX from the critical path. Note
`ResumeVersion.latex_source` is currently `NOT NULL`, so this needs a migration
plus an upload endpoint — it is real work, not a config flag.

## Working alongside Codex

`AGENTS.md` is Codex's entry point into this repo, and both tools commit to
`main` at the same time. It defers to this file for everything about the
project and adds the **lane ownership** split that keeps the two from editing
the same files at once:

- **Codex owns the pivot lane** — `app/config.py` role taxonomy,
  `app/models/job.py` (`JobFamily`), `app/discovery/**`, `companies.example.yaml`,
  `backend/templates/resumes/*.tex`.
- **Claude Code owns the usability lane** — `frontend/**`, `app/routers/**`,
  `app/schemas/**`, `app/profile.py`, `app/materials/uploads.py`, `README.md`,
  `scripts/setup.py`, `docker-compose.yml`.
- **Shared, coordinate first** — `CLAUDE.md`, `AGENTS.md`,
  `app/materials/prepare.py`, `backend/pyproject.toml`.

Two cross-lane traps: `JobFamily` also keys the resume templates *and*
`frontend/src/api/types.ts` (`JOB_FAMILIES`), and `types.ts` is hand-synced with
the backend schemas. Either change edits every side in one commit.

`git pull --rebase` before starting and before pushing; never force-push. When
this file changes in a way Codex must follow, update `AGENTS.md` in the same
session.

## Architecture

- `backend/` — FastAPI + SQLAlchemy + Alembic, SQLite (`backend/econpilot.db`, gitignored).
  - `app/routers/` — HTTP endpoints (`jobs.py`, `applications.py`, `scan.py`, …).
  - `app/discovery/` — job discovery. `scan.py` orchestrates; `sources/` holds one
    client per ATS (`greenhouse`, `lever`, `ashby`, `workday`, `github_repo`);
    `pipeline.py` normalizes/dedups/ingests; `scoring.py` scores fit.
  - `app/discovery/ats_resolve.py` — *passive* ATS classification from a job URL.
  - `app/discovery/ats_probe.py` — *active* name→ATS resolver (probes GH/Lever/Ashby
    by company-name slug). Runs at the start of each scan; one-off script at
    `scripts/resolve_unknown_ats.py`.
  - `app/materials/` — LaTeX resume tailoring + cover-letter generation (LLM).
  - `app/models/` — ORM models. `app/schemas/` — Pydantic API schemas (kept in
    sync **by hand** with `frontend/src/api/types.ts` — update both together).
- `frontend/` — React + TypeScript + Vite + Tailwind, retro-terminal dashboard.
  - `src/api/types.ts` is hand-written from the backend schemas (no codegen).
  - `src/pages/QueuePage.tsx` + `src/components/queue/` — the job queue & filters.
  - The mode toggle (`src/lib/mode.ts`) scopes every view to `internship` or
    `full_time`; its value **is** the API `role_type`. **This internship/full_time
    split stays** — it's orthogonal to the tech→econ pivot.

## Where things stand — 2026-09-10

`~/Documents/.agent/projects/econpilot.md` is the rolling truth; read it at
session start. This section is the durable shape of the work, not a status feed.

**The econ pivot is done.** `JobFamily` is `finance` / `consulting` /
`data_analytics` / `corporate` / `policy_research` / `other`, with qualified
classification — strong title phrases match directly, while generic stems
(analyst, associate, intern, research assistant) need domain evidence from the
title or description, so engineering, retail and marketing fall through to
`other`. `discovery_econ_only` (formerly `discovery_tech_only`) applies to
internships as well as full-time. The roster is 18 econ employers. Scoring is a
100-point deterministic score over skill overlap, coursework fit,
family-qualified experience, preferred family, target employer and recency, and
it still works with no LLM key. Resume templates are cut along the econ families.

**Discovery recall is the live problem.** Aiden, 2026-09-09: *"although it does
work, it just isn't what i want it to be."* Two distinct causes, and it is worth
keeping them apart:

1. **EconPilot reaches employers through the back door.** It queries ATS board
   APIs students have never heard of. Students experience the job market as
   Simplify, LinkedIn, Handshake and GitHub lists. Partly answered by handing
   the current search off to those sites (below), but EconPilot's own queue is
   only as wide as the boards it can read.
2. **Roster-bound recall.** Only companies in `companies.yaml` with a resolved
   ATS get scanned. Tenant enumeration (`backend/scripts/enumerate_ats_tenants.py`)
   raises the ceiling, but its output is unreachable — see the next section.

### The recurring failure mode: shipped but Aiden-only

This is the thing to watch for in this repo. Three capabilities are built,
tested and working, and none of them can be used by the person EconPilot is for:

- **ATS candidates.** The enumerator writes `ats_candidates.yaml`. Acting on it
  means running a script and hand-merging YAML into `companies.yaml`.
- **USAJOBS discovery.** Inert unless `usajobs_api_key` and `usajobs_user_agent`
  are set in `backend/.env`, and it fails silent when they are not.
- **Base resumes.** Still LaTeX (`backend/templates/resumes/*.tex`, `tectonic`).

A feature in this state is **not shipped**. When the pivot lane lands a
capability, the usability lane's job is to give it a screen — that pairing is
the whole reason the lanes exist. The Profile page is the reference pattern:
file stays the storage, screen becomes the interface, and the API reports when a
config is still un-personalized (`is_placeholder`).

### Next steps — usability lane (Claude Code)

In order. Each is a commit-and-push unit.

1. **ATS candidate review screen.** `GET /companies/candidates` reads
   `ats_candidates.yaml`; a screen lists each discovered board with its employer
   name and lets the user accept or reject it, writing accepted rows into
   `companies.yaml` the way `PUT /profile` rewrites `profile.yaml`. Run the
   enumeration from the app with visible progress — a multi-minute silent probe
   reads as a hang. This unblocks the single largest recall win already built.
2. **USAJOBS credentials in the UI**, with a plain-language note on requesting
   the free key, and a visible state when discovery is running without it
   instead of quietly returning nothing.
3. **PDF résumé upload**, retiring LaTeX from the critical path. Users tag 2-3
   finished PDFs with a role family, matching the pre-built-resume design.
   Needs a migration: `ResumeVersion.latex_source` is `NOT NULL`.
4. **`companies.yaml` and the LLM key into the UI**, completing the move of
   every personalizable config off the filesystem.

### Next steps — pivot lane (Codex)

Detailed in `AGENTS.md`, which is Codex's entry point and carries the live
handoff. Summary, in order: a **README-table source client** (the econ community
repos publish markdown tables, not `listings.json` — verified 2026-09-09, so
this is a parser, not config) pointed at the finance/accounting/quant lists;
then **Workday tenant resolution** to unblock the banks and consulting firms
sitting at `unknown` in the roster.

### Standing constraint: dedup and ghost listings

Every source added multiplies the chance the same role arrives twice, and these
lists keep dead postings around. `dedup_hash` was sized for one source per job.
Each new source ships with its `posted_at` reliability documented and its dedup
behaviour tested against a source already in the pipeline. **A queue full of
duplicates and dead postings is worse than the narrow queue we have now** — and
unlike narrowness, it is the kind of wrong that makes a non-technical user stop
trusting the tool.

### Settled: how EconPilot reaches LinkedIn, Indeed and Handshake

**By building the query and handing off, never by scraping.** None of them
exposes a job-search API we may call; scraping breaches their terms and gets the
user's own IP blocked, and EconPilot runs on the student's laptop, so they would
eat that block. `frontend/src/lib/jobSearchLinks.ts` turns the queue's field,
location, mode and search box into a pre-filled LinkedIn or Indeed search,
falling back to the profile city when the location box is empty.

Two details worth preserving if that file is touched: family names are
translated into words a posting would actually use (`policy_research` →
"economic policy research"), because searching a site for our enum name returns
nothing. And **Handshake links to its search page unfiltered on purpose** — it
is per-school, behind a login, and its filter params are numeric ids that differ
between schools, so no link we could build would filter correctly for everyone.
The hover text says so. An honest plain link beats params that silently do
nothing.

## Running the app

Backend (port 8000) — **always launch with `--reload`**:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

⚠️ A process started **without** `--reload` will silently serve stale code after
edits (this bit JobPilot once — a 500 because the running server predated a model
change). To restart: `lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill`, relaunch, then
confirm `curl -s localhost:8000/health` → `{"status":"ok","db":"ok"}`.

Frontend (port 5173, hot-reloads on its own): `cd frontend && npm run dev`

### First-time setup (fresh fork — deps and DB were not copied)

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e .
cp ../.env.example .env          # then fill LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
.venv/bin/alembic upgrade head   # creates a fresh econpilot.db
cd ../frontend && npm install
```

## Commands

- Backend tests: `cd backend && .venv/bin/pytest` (asyncio auto-mode; `latex` and
  `agent` marked tests need real tectonic / Chromium).
- Backend migrations: `.venv/bin/alembic upgrade head`; new migration files go in
  `backend/alembic/versions/` (match the existing revision-chain style).
- Frontend: `npm run test` (vitest), `npm run lint` (oxlint), `npm run build`
  (`tsc -b && vite build` — run `npx tsc --noEmit` to typecheck without building).
- Seed companies: `.venv/bin/python scripts/seed_companies.py`.

## Conventions & gotchas

- **Keep `frontend/src/api/types.ts` in sync with `backend/app/schemas/*`** — there
  is no codegen. Changing an API shape means editing both.
- Discovery is **freshness-bounded** (`scan_max_age_days`, default 21). It is also
  scoped to econ roles by `discovery_econ_only` in `app/config.py`, which applies
  to internships as well as full-time. Set it false to ingest everything for
  manual review.
- Only companies with a **known ATS** are scanned; `unknown` ones are skipped.
  Workday tenants and custom career sites can't be resolved from a name alone and
  remain unscannable — resolving them needs following the careers-page redirect to
  discover the Workday `host|site` coordinate (not yet built). This matters more
  for econ: many banks/consulting firms run Workday.
- The browser agent must **never auto-submit** — it stops at the review step.
- LLM is configured via `backend/.env` (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`;
  currently OpenRouter). Discovery and scoring work without it; Prepare/agent need it.
- Commits go directly to `main` (solo repo). `pre-commit` runs gitleaks + hygiene hooks.

### Git remote & commit cadence (not optional)

The remote is **`origin` = https://github.com/A319K/econpilot.git**, and it is a
**public** repo. Two consequences:

- **Commit and push as you go.** Every logical unit of work ends with a commit
  on `main` and a `git push`. Do not batch a whole session into one giant commit,
  and do not leave the session with unpushed commits or a dirty tree — the
  remote is the backup, and `~/Documents` is iCloud-synced, not versioned.
  Message style: imperative subject describing the change ("Re-target discovery
  keywords to econ role families"), matching the existing history.
- **Public repo — nothing personal goes in.** `.gitignore` already excludes
  `.env`, `companies.yaml`, `profile.yaml`, `*.db`, `output/`, and `/Resume.pdf`.
  Before adding any new file that holds a key, a real company roster, resume
  text, or anything with Aiden's name/contact in it, ignore it instead of
  committing it. `pre-commit`'s gitleaks hook is the second line of defense, not
  the first.

---

## Master-agent protocol (applies to Claude Code AND Codex)

This project is tracked by the master agent at `~/Documents`. Two obligations:

**At session start** — read `~/Documents/.agent/projects/econpilot.md` for status,
next step, and blockers, plus the last few entries for this project in
`~/Documents/.agent/log/sessions.jsonl`. Don't re-derive state from the code.

**At session end** — report back. Append one record:

```bash
python3 ~/Documents/.agent/bin/log_session.py \
  --project econpilot --tool <claude-code|codex> \
  --actual-minutes <n> --focus <1-5> \
  --did "what concretely changed" \
  --next "the concrete first action for next time" \
  --blockers "comma,separated"
```

Then rewrite `~/Documents/.agent/projects/econpilot.md` — `last_touched`, **Status**,
**Next step**, **Blockers**.

`--next` must name a concrete first action. It becomes the opening line of a
scheduled calendar block, and starting is the hard part. "Continue working on
it" is rejected by the logger.

This is in addition to — never instead of — this project's own logging
conventions described above.
