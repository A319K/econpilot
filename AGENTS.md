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

- `backend/app/config.py` — role taxonomy, keyword/title logic, `discovery_tech_only`
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
cd backend && .venv/bin/pytest -m "not latex and not agent"   # 497 passing
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

*Last updated 2026-09-07.*
