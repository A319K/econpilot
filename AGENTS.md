# AGENTS.md — EconPilot, for Codex

This file is for **Codex**. Claude Code works in the same repository at the same
time, so the rules below exist mainly to keep the two of you from editing the
same files in the same hour.

## Read CLAUDE.md first

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

## Current handoff — 2026-09-09 (Claude Code → Codex)

Your 2026-09-08 run landed both units from the previous handoff — roster
(`fb4c01f`) and econ scoring (`9ee09ef`, a 100-point score over skill overlap,
coursework fit, family-qualified experience, preferred family, target employer,
and recency). You logged the session properly. Nothing is outstanding from it.

Claude Code shipped one fix in the usability lane on 2026-09-09, `5a434ae`:
`sort=recent` on `GET /jobs` ordered by `discovered_at`, so every job from a
single scan shared one timestamp and the queue's age column came out scrambled.
It now orders by `coalesce(posted_at, discovered_at)` — what the column actually
renders. Two tests in `backend/tests/test_jobs_api.py`. Suite is 506 passing.

**This handoff changes your next step.** You logged `--next` as the USAJOBS
adapter. That work is still wanted, but it drops to item 2 — read item 1 first.

### The problem this handoff is about

Aiden's assessment on 2026-09-09: discovery is too narrow. Not wrong — narrow.
The queue does not surface enough for it to be worth opening.

The cause is structural, so adding companies one at a time will not fix it.
**EconPilot is roster-bound**: it scans only companies present in
`companies.yaml` *and* carrying a resolved ATS. That is 11 scannable boards
today, so the ceiling on recall is the roster, and raising the ceiling is linear
manual work forever.

For contrast, jobright.ai aggregates ~8M listings and ~400k new postings a day
from career sites and the big boards, refreshed every few minutes, and is
explicitly a **matching-and-autofill layer over aggregated listings rather than
a job board**. Recall comes free in that model; precision and ghost-listing
filtering are the hard parts.

We are not copying that. Two reasons, both binding:

- **EconPilot is local-first.** It runs on a friend's laptop. It cannot host an
  8M-row corpus, and it should not try. What it needs is good *recall on econ
  roles*, not coverage of the labor market.
- **Scraping LinkedIn/Indeed/Glassdoor is against their terms** and gets
  IP-blocked quickly. A funded company absorbs that risk; software Aiden hands
  to friends must not. Official APIs and published files only. If a source's
  terms prohibit automated collection, the integration is a **user-initiated
  import**, not a crawler — see AEA JOE below.

So the goal is to flip discovery from *"companies I have listed"* toward
*"roles matching my search"*, using sources that permit it.

### 1. Tenant enumeration — do this first

The largest recall multiplier available on code that already exists.
`app/discovery/ats_probe.py` already resolves a company name to a
Greenhouse/Lever/Ashby board by slug. Today it runs over a hand-written roster.
Point it at a large employer list instead and let it discover boards wholesale:
econ-consulting directories, asset managers, the Fortune/Forbes rosters, think
tanks. Board tokens are public and slug-guessable, which is the whole reason the
probe works.

Design notes:

- This should produce **roster candidates, not silent ingestion**. A resolved
  board is a suggestion; keep `is_target` and user curation meaningful. A
  discovery run that quietly triples the queue with employers the user never
  chose is a worse product, not a better one.
- Rate-limit and cache aggressively. Probing thousands of slugs from a laptop
  will get throttled, and every user runs their own copy against the same
  endpoints — there is no shared server absorbing this.
- Persist negative results. Re-probing known-dead slugs every scan is the
  obvious way to make this slow.
- Report progress. A multi-minute probe with no output reads as a hang to a
  non-technical user, and every error message is user-facing copy (CLAUDE.md).

### 2. USAJOBS — your original next step, unchanged

A real public API, and the front door for federal Economist (GS-0110), BLS, BEA,
CBO. Model it on the `github_repo` client: a non-ATS source feeding the same
normalize/dedup/score pipeline. Your logged plan — adapter contract plus
fixtures in `backend/app/discovery/sources/`, then pipeline integration — is
right; just do it after item 1.

### 3. AEA JOE — the highest-signal econ source, via import not crawl

**Job Openings for Economists** (`aeaweb.org/joe/listings`) is *the* economics
job market: ~1,700 positions filled a year, and the main channel for pre-docs and
academic-adjacent roles. For an econ-major audience this is more on-target than
any general board.

**The AEA prohibits scraping or redistributing site content**, but publishes
current listings as a downloadable XLS. So the integration is: the user downloads
the file and imports it. That respects the terms, fits local-first, and needs no
credentials.

This one is **cross-lane**. Yours is the parser and the mapping from JOE rows
into `RawJob` so it flows through the existing pipeline. The upload endpoint and
the screen are Claude Code's (`app/routers/`, `frontend/`). Define the `RawJob`
mapping and say so in your session log; Claude Code will build the intake around
it.

### 4. Workday tenant resolution

Unblocks the 7 `unknown` roster entries and most banks and consulting firms —
the highest ceiling for finance roles specifically, and the hardest item here.
Needs following a careers-page redirect to recover the `host|site` coordinate,
which cannot be derived from a company name. Treat it as its own unit and take
it last of these four.

### 5. Only if the above is not enough: keyword-queryable aggregators

Adzuna has a documented API; Google Jobs is reachable via SerpAPI. These are the
real shape-change — search-driven rather than roster-driven. Held back to last
because both add an API key to setup, and **nothing requiring a paid signup may
gate the core loop** (CLAUDE.md). If added, they are an upgrade path, clearly
marked, with discovery still fully functional without them.

### The thing that gets harder as soon as any of this lands

**Dedup and freshness become the quality bottleneck.** Once the same role
arrives from three sources, `dedup_hash` is doing work it was not sized for, and
ghost listings — postings left up for months — start filling the queue. That is
precisely why jobright ships a dedicated ghost filter. `scan_max_age_days`
helps but leans on `posted_at`, which aggregators report inconsistently or not
at all.

Treat this as part of the work, not as follow-up: every source added should come
with its `posted_at` reliability documented and its dedup behaviour tested
against a source already in the pipeline. A queue full of duplicates and dead
postings is a worse outcome than the narrow queue we have now.

### What Claude Code is doing meanwhile

Usability lane — PDF résumé upload to get LaTeX off the critical path (needs a
migration; `ResumeVersion.latex_source` is `NOT NULL`), moving `companies.yaml`
and the LLM key into the UI on the Profile page pattern, the one-step install
path, and the JOE import screen once you have defined the mapping in item 3.

### Earlier history

`0e51d4e` (2026-09-07) re-targeted the role taxonomy: `JobFamily` became
`finance` / `consulting` / `data_analytics` / `corporate` / `policy_research` /
`other`, with qualified classification — strong title phrases match directly,
generic stems (analyst, associate, intern, research assistant) require domain
evidence from title or description, so engineering, retail, nursing and
marketing fall through to `other`. `discovery_tech_only` became
`discovery_econ_only` and now applies to internships too; ATS sweeps were
restored for internship scans with the inherited GitHub tech feed demoted to
supplemental and filtered through the econ classifier. Migration
`a7b8c9d0e1f2`; `frontend/src/api/types.ts` and the five econ resume templates
were re-cut alongside it.

`fb4c01f` (2026-09-08) seeded the econ roster: 18 employers, 11 scannable
Greenhouse/Ashby boards verified HTTP 200 on 2026-09-07, 7 high-value
Workday/custom targets left `unknown` so they stay visible until item 4 lands.

Operational note, still true: this repository lives under iCloud-synced
`~/Documents`, which stalled Git on offloaded `.git/objects` during the
2026-09-07 session. Active repos belong in a local path such as `~/Developer`.
Ask Aiden before moving it — `~/Documents/CLAUDE.md` maps `econpilot/` and would
need updating in the same change.

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
cd backend && .venv/bin/pytest -m "not latex and not agent"   # 506 passing
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
