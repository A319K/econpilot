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

## Current handoff — 2026-09-08 (Claude Code → Codex)

Your 2026-09-07 handoff is preserved below under "What landed on 2026-09-07".
Read it — nothing in it is stale. This section is what to do next.

Housekeeping done for you on 2026-09-08 so you can start on code:

- Your 2026-09-07 session is now logged in
  `~/Documents/.agent/log/sessions.jsonl` (backdated, marked as logged
  retroactively by Claude Code — you never ran checkout).
- `~/Documents/.agent/projects/econpilot.md` was rewritten. It had still said
  "just forked, next step: re-target the taxonomy," which you'd already done.
  It now carries the real status, next step, and the three live blockers.

Nothing was committed on your behalf and nothing in your lane was edited. Your
three uncommitted files are untouched — `companies.example.yaml`,
`backend/tests/test_seed_companies.py`, and this `AGENTS.md` (this section is the
only change to it). Preserve them through any pull or cleanup.

### 1. Land the roster unit — first, before anything else

It is finished and verified; only the commit failed. Do not redo the work.

```bash
git status --short          # expect exactly the three files above
git pull --rebase
cd backend && .venv/bin/pytest -m "not latex and not agent"
git add companies.example.yaml backend/tests/test_seed_companies.py AGENTS.md
git commit -m "Seed an economics-oriented employer roster"
git push
```

If iCloud stalls git again on offloaded `.git/objects`, that is the known
blocker, not a new bug. Two ways through, in order of preference:

- **Move the repo off iCloud** — `mv ~/Documents/econpilot ~/Developer/econpilot`
  (`mv`/`cp -a` on the whole directory, never by dragging contents in Finder;
  `.git`, `.claude` and dotfiles do not survive a ⌘A drag). Then commit from the
  new path. Update `dir:` in `~/Documents/.agent/projects/econpilot.md` if you do.
  **Ask Aiden before moving it** — the master agent's map in
  `~/Documents/CLAUDE.md` points at `econpilot/` and would need updating too.
- **Or** `Keep Downloaded` on the repo folder to force objects local, then retry.
  This unsticks the commit but is not a fix; the move is.

If neither works, stop and report rather than force-adding or re-cloning.

### 2. Retune scoring for econ — the main work

`backend/app/discovery/scoring.py` still weights software-engineering signals.
Re-tune around what actually predicts fit for an econ major:

- **Coursework** — econometrics, statistics, macro/micro theory, financial
  accounting, calculus/linear algebra.
- **Quant & finance skills** — Stata, R, Python (pandas), SQL, Excel modeling,
  valuation/DCF, Bloomberg. Note Excel is a *real* positive signal here in a way
  it never was for SWE.
- **Target-role fit** — how well the posting's `JobFamily` matches the user's
  stated targets in `profile.yaml`.
- **Relevant experience** — internships in finance/consulting/research, RA work,
  case-competition and investment-club signals.

Two things to respect while you do it. Scoring must keep working with **no LLM
key** — it is part of the deterministic core loop that has to stay usable
without a paid signup. And expect the noise the taxonomy work already found:
"analyst" and "associate" are everywhere, so the score should reward domain
evidence rather than assume the classifier caught everything.

### 3. Then, in order

- Replace or disable the inherited Simplify tech feeds once an econ-specific
  internship/new-grad source exists. Until then they stay supplemental and
  filtered, which is the current state — don't remove them without a
  replacement, or internship scans lose coverage.
- Add sources for the high-value unscannable paths: **USAJOBS** (federal
  Economist, GS-0110), **Federal Reserve RA** postings, **NBER**/EconJobMarket
  pre-docs, and **Workday**-hosted banks and consulting firms. Model the first
  three on the existing `github_repo` source client — a non-ATS source feeding
  the same pipeline. Workday is the hard one: it needs following a careers-page
  redirect to discover the `host|site` coordinate, which is why those 7 roster
  entries sit at `unknown`. Treat it as its own unit, last.

### What Claude Code is doing meanwhile

Usability lane only — PDF résumé upload to replace the LaTeX templates on the
critical path (needs a migration; `ResumeVersion.latex_source` is `NOT NULL`),
moving `companies.yaml` and the LLM key into the UI following the Profile page
pattern, and the one-step install path. **The PDF-upload work will touch how
resumes are keyed by `JobFamily`** — the same cross-lane trap flagged above. If
you change `JobFamily` again, say so in your session log before you start.

### What landed on 2026-09-07

Codex completed and pushed the first economics-pivot unit in commit `0e51d4e`
(`Re-target job taxonomy to economics roles`):

- Replaced the tech `JobFamily` values with `finance`, `consulting`,
  `data_analytics`, `corporate`, `policy_research`, and `other`.
- Added qualified econ-role classification. Strong title phrases match directly;
  generic titles such as analyst, associate, intern, or research assistant need
  domain evidence from the title or description. Unrelated engineering, retail,
  nursing, and marketing roles remain `other`.
- Replaced `discovery_tech_only` with `discovery_econ_only`. The default filter
  now applies to internships as well as full-time jobs.
- Restored ATS sweeps for internship scans. The inherited GitHub internship feed
  is tech-oriented and is supplemental only; it is filtered through the same
  econ classifier.
- Added Alembic migration `a7b8c9d0e1f2`, synchronized
  `frontend/src/api/types.ts`, updated resume upload defaults and seed logic, and
  replaced the three tech LaTeX examples with five econ-family examples.
- Verification passed: 499 supported backend tests, TypeScript typecheck, 23
  frontend tests, lint with five pre-existing warnings, and migration
  upgrade/downgrade/upgrade including legacy-value conversion.

Codex also prepared the next roster unit in the working tree, but it is **not
committed yet** because iCloud repeatedly stalled Git while reading offloaded
`.git/objects` files:

- `companies.example.yaml` now contains 18 economics-oriented employers: 11
  directly scannable Greenhouse/Ashby boards and 7 high-value targets awaiting
  Workday/custom-source support.
- All 11 configured ATS board ids returned HTTP 200 from their official APIs on
  2026-09-07, and `backend/tests/test_seed_companies.py` passes (4 tests).
- The only uncommitted files should be `companies.example.yaml`,
  `backend/tests/test_seed_companies.py`, and this `AGENTS.md` handoff. Preserve
  them; do not overwrite them during a pull or cleanup.

Operational note: this repository currently lives under iCloud-synced
`~/Documents`. Active Git repositories should instead live in a local working
directory such as `~/Developer`, with GitHub for committed source and Time
Machine for uncommitted/private state. `Keep Downloaded` reduces iCloud stalls
but is not a backup.

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
cd backend && .venv/bin/pytest -m "not latex and not agent"   # 499 passing
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

*Last updated 2026-09-08.*
