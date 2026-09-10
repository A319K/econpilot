# AGENTS.md — EconPilot, for Codex

This file is for **Codex**. Claude Code works in the same repository at the same
time, so the rules below exist mainly to keep the two of you from editing the
same files in the same hour.

## Read CLAUDE.md first

`CLAUDE.md` gained a **"Where things stand"** section on 2026-09-10 carrying the
current state of the pivot, the two causes of the recall problem, the
shipped-but-Aiden-only failure mode, and both lanes' next steps. Read it before
this file's handoff — the handoff assumes it.

`CLAUDE.md` is the shared authority for this project: what EconPilot is, the
architecture, how to run it, the tech→econ pivot, and the settled scope
decisions. **It is not Claude-only — read it, follow it, and treat it as
binding.** This file does not repeat it; it adds the coordination rules.

Two facts from it that shape every decision, repeated here because they are easy
to miss:

1. **EconPilot is a fork of JobPilot being re-targeted from software-engineering
   roles to economics roles.** The engine is role-agnostic; what makes it "tech"
   is config and data. Treat leftover tech-specific behavior as something to
   change, not preserve.
2. **The users are Aiden's econ-major friends, not developers.** They can open a
   terminal and paste a command. They will not open a code editor to hand-edit a
   config file, write LaTeX, or read a stack trace. Anything a user must
   personalize belongs on a screen in the app, not in a YAML file.

## Lane ownership (the important part)

Both agents commit to `main` in the same repo. Stay inside your lane; if a task
needs a file from the other lane, say so in your session log rather than
reaching across.

**Codex owns the pivot lane — the econ re-targeting:**

- `backend/app/config.py` — role taxonomy, keyword/title logic, `discovery_econ_only`
- `backend/app/models/job.py` — the `JobFamily` enum
- `backend/app/discovery/` — `scoring.py`, `pipeline.py`, `sources/`
- `companies.example.yaml` — the seed employer roster
- `backend/templates/resumes/*.tex` — base resume templates (keyed by `JobFamily`)

**Claude Code owns the usability lane — making it installable by a non-developer:**

- `frontend/` — all pages and components
- `backend/app/routers/`, `backend/app/schemas/`, `backend/app/profile.py`
- `backend/app/materials/uploads.py`
- `README.md`, `scripts/setup.py`, `docker-compose.yml`

**Shared, so coordinate before touching:** `CLAUDE.md`, this file,
`backend/app/materials/prepare.py`, `backend/pyproject.toml`.

### The two cross-lane traps

- **`JobFamily` is not local to your lane.** It keys the resume templates and is
  mirrored in `frontend/src/api/types.ts` as `JOB_FAMILIES`. Changing it means
  changing all three **in one commit**, plus a migration if stored values change.
  Flag it in your session log — it is the most likely place for the two agents to
  collide.
- **`frontend/src/api/types.ts` is hand-synced with `backend/app/schemas/*`.**
  There is no codegen. An API shape change edits both sides in the same commit.

## Current handoff — 2026-09-09 evening (Claude Code → Codex)

Your three commits are verified and nothing is outstanding from them:
`158929f` (ATS tenant enumeration), `7fc2ae8` (optional USAJOBS), `6c29f4c`
(handoff). AEA JOE stays declined — do not build it.

Claude Code shipped two units in the usability lane today:

- `5a434ae` — `sort=recent` ordered by `discovered_at`, so a whole scan shared
  one timestamp and the queue's age column looked scrambled. Now
  `coalesce(posted_at, discovered_at)`, which is what the column renders.
- `7a9e0b2` — queue filters reworked (see "Filter changes" below). This added
  a `location` query param to `GET /jobs`; `frontend/src/api/types.ts` was
  updated in the same commit.

**Aiden has redirected the discovery work.** Workday tenant resolution is *no
longer the next unit*. Read the new direction before starting anything.

### The new direction, in Aiden's words

> "although it does work, it just isn't what i want it to be. can we try a
> different approach. can we use things that college students are more likely to
> use such as simplify, linkedin, githubs, etc."

The read: EconPilot has been reaching employers through the back door — ATS
board APIs the user has never heard of. Students do not experience the job
market that way. They experience it as a handful of well-known surfaces. Meeting
them there matters more than another tenant resolver.

This reframes recall as a *product* problem, not only a coverage problem.

### What is already true, and what it costs

**Simplify is already wired.** `github_repo` reads
`SimplifyJobs/Summer2026-Internships`. It is the tech list, filtered through the
econ classifier, which is why it contributes little here. The mechanism Aiden is
asking for exists; it is pointed at the wrong repos.

**The econ-relevant community repos do not publish `listings.json`.** Verified
2026-09-09: `jobright-ai/2026-Account-Internship` (accounting and finance) ships
its Daily Job List as a **markdown table in README.md** — company, job title,
location, work model, date posted — with no JSON or CSV anywhere in the repo.
`northwesternfintech/2027QuantInternships` is the same shape. Our source client
deliberately reads structured `listings.json` and not the README.

So this is **a new parser, not a config change**. That is the main piece of work
in item 1 and the reason it is not a one-line `.env` edit.

### 1. A README-table source client, then point it at econ repos

Add a source that parses the markdown-table format these repos share, and feed
it through the existing normalize/dedup/score pipeline like `github_repo`.

Repos worth carrying (verify each is live and current before committing — they
rotate every season, which is why the existing feed config is already
`.env`-overridable):

- `jobright-ai/2026-Account-Internship` — accounting and finance
- the sibling `jobright-ai/*-Internship` repos covering data analyst and
  business/finance functions
- `northwesternfintech/2027QuantInternships` — quant
- the Simplify/CSCareers general lists we already read, kept as-is

Parsing notes, from looking at the actual tables:

- Rows carry **relative or short dates** ("Sep 08"), not the absolute timestamps
  `listings.json` gives us. `posted_at` reliability is therefore lower, which
  matters because `sort=recent` and `scan_max_age_days` both depend on it.
  Document what you can infer and leave `posted_at` null rather than guessing a
  year — a wrong date is worse than none, since it silently reorders the queue.
- Company and title arrive as **markdown links**, often with emoji and badge
  images mixed in. Strip to text before dedup or the hash will differ from the
  same role arriving via ATS.
- These lists overlap heavily with each other and with our ATS sweeps. **Dedup
  is the whole ballgame here**, not an afterthought — see the standing note
  below.

### 2. LinkedIn — the honest version, and it is not a scraper

There is no legitimate programmatic path. LinkedIn has no public job-search API
for this use case, and scraping breaches their terms and gets IP-blocked
quickly. We are not doing it: this is software Aiden hands to friends, running
on their own laptops and their own IPs.

What we *can* do gives most of the value: **generate pre-filled search links**
into LinkedIn, Indeed and Handshake from the user's profile and current filters,
and let them click through. The student stays on the surface they already trust,
we do the query construction, and nothing is scraped or stored.

That is a frontend job, so **Claude Code owns it** — no work for you here beyond
not building a crawler. Handshake deserves a note: it is the channel most
college students actually use, but it is per-school and auth-walled, so
deep-linking is the only option there too.

### 3. Workday tenant resolution — still wanted, now after item 1

Unchanged in substance and still the highest ceiling for banks and consulting
firms; it just is not the next thing. Follow the careers-page redirect to
recover the `host|site` coordinate. Take it once the README-table source is in.

### Filter changes that touch your lane's assumptions

`7a9e0b2` reworked the queue filter bar, and one change is load-bearing for you:

- **The source filter is gone.** Which ATS a posting came from is internal
  plumbing, not something a user chooses by. `JobSource` is still on the model,
  still filterable via the API, and still worth setting correctly — it just is
  not surfaced. Do not add UI for it.
- Job family is now a single dropdown with plain-language labels ("data &
  analytics", "policy & research") rather than a row of raw enum toggles, and it
  filters server-side via the existing `job_family` param.
- Location is a new server-side `location` param on `GET /jobs`, matched
  case-insensitively as a substring because ATS location strings are free text
  ("Boston, MA (Hybrid)", "Remote - US").

The last one is a request: **whatever a new source writes into `Job.location`
is now user-visible and user-filterable.** Normalize it to something a person
would type. A row that stores "US-MA-Boston-Seaport" will not be found by
someone typing "boston".

### The standing requirement, restated because item 1 makes it urgent

**Dedup and ghost listings decide whether this helps or hurts.** Community
repos, ATS sweeps and USAJOBS will return the same role, and these lists keep
dead postings around. `dedup_hash` was sized for one source per job. Every
source added ships with its `posted_at` reliability documented and its dedup
behaviour tested against a source already in the pipeline.

A queue full of duplicates and dead postings is a worse outcome than the narrow
queue we have now — and unlike narrowness, it is the kind of wrong that makes a
non-technical user stop trusting the tool.

### What Claude Code is doing meanwhile

The pre-filled search links in item 2; a review screen for the ATS candidates
your enumerator writes to `ats_candidates.yaml` (today a user would have to run
a script and hand-edit YAML, which the audience cannot do); moving the USAJOBS
credentials out of `.env` and into the UI with a plain-language note on
requesting the key; and PDF résumé upload to get LaTeX off the critical path.

### Earlier history

`0e51d4e` re-targeted the taxonomy (`JobFamily` → finance / consulting /
data_analytics / corporate / policy_research / other, qualified classification,
`discovery_tech_only` → `discovery_econ_only`, migration `a7b8c9d0e1f2`).
`fb4c01f` seeded the 18-employer econ roster (11 scannable, 7 Workday/custom
left `unknown`). `9ee09ef` retuned scoring into a 100-point deterministic score
over skill overlap, coursework fit, family-qualified experience, preferred
family, target employer and recency. `158929f` added tenant enumeration writing
review candidates to `ats_candidates.yaml`. `7fc2ae8` added optional USAJOBS
discovery behind `usajobs_api_key` / `usajobs_user_agent`.

Operational note, still true: this repo lives under iCloud-synced `~/Documents`,
which stalled Git on offloaded `.git/objects` on 2026-09-07. Active repos belong
in a local path such as `~/Developer`. Ask Aiden first — `~/Documents/CLAUDE.md`
maps `econpilot/` and would need updating in the same change.

## Git

The remote is `origin` → https://github.com/A319K/econpilot (**public**).

- `git pull --rebase` before you start, and again before you push.
- Commit each logical unit and **push it** — don't leave work sitting locally.
  Short commits reduce the blast radius when both agents are active.
- Never force-push or rewrite pushed history. The other agent may have built on it.
- If you hit a conflict in a file outside your lane, don't resolve it by
  overwriting — the other agent probably meant it. Take their version and note it.
- **Nothing personal or secret gets committed.** `.gitignore` already excludes
  `.env`, `profile.yaml`, `companies.yaml`, `*.db`, `output/`, `/Resume.pdf`.
  New files with keys, a real company roster, or résumé content get ignored, not
  committed. `pre-commit` runs gitleaks as a backstop, not as the first line.

## Verify before you commit

```bash
cd backend && .venv/bin/pytest -m "not latex and not agent"   # 524 passing
cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run test -- --run && npm run lint
```

Running the app (backend needs `--reload`, or it silently serves stale code):

```bash
cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend && npm run dev     # http://localhost:5173
```

⚠️ Port 8000 and 8001 are sometimes taken by Aiden's other projects. If
`Address already in use` appears, **use another port** — don't kill the process,
it is probably a different app of his.

## Don't rebuild these (settled — see CLAUDE.md)

- **Gmail auto-status tracking is out of scope.** A misread email silently
  corrupts the tracker, which is worse than updating it by hand.
- **Per-job resume rewriting stays off.** `prepare_tailor_default` is `False` on
  purpose: Prepare picks the best-fit pre-built base resume. Aiden's model is
  2-3 role-specific resumes, not a fresh one per application.
- **The browser agent never auto-submits.** It stops at review so the user clicks
  submit. This is not negotiable.

## Report back when you finish

Same protocol as Claude Code — the master agent at `~/Documents` reads plain
files, so both tools participate by following the same steps.

**At session start**, read `~/Documents/.agent/projects/econpilot.md` and the
recent econpilot entries in `~/Documents/.agent/log/sessions.jsonl`. Don't
re-derive state from the code.

**At session end**, append one record and then rewrite the project file
(`last_touched`, Status, Next step, Blockers):

```bash
python3 ~/Documents/.agent/bin/log_session.py \
  --project econpilot --tool codex \
  --actual-minutes <n> --focus <1-5> \
  --did "what concretely changed" \
  --next "the concrete first action for next time" \
  --blockers "comma,separated"
```

`--next` must name a real first action — "continue working on it" is rejected by
the logger. Since two agents share this repo, `--did` should also say **which
files you touched**, so the next session (either tool) can see where the edits
landed.

---

*Last updated 2026-09-09.*
