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
behavior as a thing to change (see "The pivot" below), not a thing to preserve.
At the time of the fork the codebase still behaves tech-focused until that list
is worked through.

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
- **Every error message is user-facing copy.** Assume it will be read by someone
  who cannot interpret a stack trace and will not open a log file. Say what went
  wrong and what to do next, in plain language, in the UI.
- **Terminal steps are a budget, not a free resource.** The target is one
  command (or a double-clickable script) to start, and zero after that. Every
  additional step in the README is a place a friend gets stuck and gives up.
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

## The pivot: tech → finance/econ (the actual work)

These are the tech-shaped pieces to re-target. A fresh EconPilot still finds and
scores SWE roles until they're changed. Rough priority order:

1. **Role taxonomy — `backend/app/config.py`.** The `discovery_tech_only` flag and
   the tech title/keyword logic decide what counts as a relevant posting. Econ
   roles do **not** cluster around a few clean title stems the way SWE does — they
   scatter across many functions and titles that often never say "economics."
   Re-target the keywords to econ role families:
   - **Finance/investment** — investment banking / summer analyst, sales & trading,
     equity & credit research, asset management, corporate finance / FP&A, risk.
   - **Consulting** — management/business analyst, and specifically **economic
     consulting** (NERA, Cornerstone, Analysis Group, Charles River, Brattle).
   - **Data/analytics** — data analyst, business analyst, BI, quant, pricing.
   - **Tech-adjacent econ** — product/ops analyst, and true **Economist** roles
     (Amazon/Uber/Airbnb-style).
   - **Policy & central banking** — Federal Reserve **Research Assistant** (RA),
     Treasury/CBO/BLS/BEA, think tanks (Brookings, RAND, Urban), policy analyst.
   - **Academic pipeline** — **pre-doctoral** research assistant (pre-doc), NBER.

   Expect noisy matching: "analyst"/"associate" appear everywhere, so match on
   stems (`analyst`, `associate`, `economist`, `research assistant`, `consultant`)
   qualified by domain words (`financial`, `economic`, `data`, `business`, `quant`,
   `policy`, `risk`, `investment`) and filter aggressively.

2. **Seed companies — `companies.example.yaml` (+ `companies.yaml`, gitignored).**
   Replace the tech company set with econ/finance employers: banks, consulting and
   economic-consulting firms, asset managers, think tanks, the Fed. Many use the
   **same ATS backends** (Greenhouse/Lever/Ashby/Workday) already supported, so the
   discovery plumbing transfers — only the roster changes.

3. **Scoring — `app/discovery/scoring.py`.** Fit weights are tuned for SWE
   signals; re-tune for econ (relevant coursework, finance/analytics keywords,
   target-role match) instead of software stack.

4. **Frontend copy — labels/wording** in the queue and headers that assume tech
   roles. Keep the `internship`/`full_time` mode toggle; change the vocabulary.

5. **(Later) new source clients** for flagship econ paths that aren't on standard
   ATS: **USAJOBS** (federal Economist, GS-0110), **NBER**/EconJobMarket for
   pre-docs, Fed RA postings. Model these on the existing `github_repo` source
   client (a non-ATS source that feeds the same pipeline).

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
  still **tech-focused** via `discovery_tech_only` in `app/config.py` — that is the
  legacy default to re-target for econ (see "The pivot", #1), not a setting to keep.
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
