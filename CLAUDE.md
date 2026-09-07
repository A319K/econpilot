# CLAUDE.md

Guidance for Claude Code when working in this repo. EconPilot is a **local-first**
job-application system: it discovers postings from company ATS APIs, tailors a
resume + cover letter per job with an LLM, tracks each application through a
validated pipeline, and drives a human-supervised browser agent that fills forms
and **stops at review so the user clicks submit**.

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
    `full_time`; its value **is** the API `role_type`.

## Running the app

Backend (port 8000) — **always launch with `--reload`**:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

⚠️ A process started **without** `--reload` will silently serve stale code after
edits (this caused a 500 on the intern queue once — the running server predated a
model change). To restart: `lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill`, relaunch,
then confirm `curl -s localhost:8000/health` → `{"status":"ok","db":"ok"}`.

Frontend (port 5173, hot-reloads on its own): `cd frontend && npm run dev`

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
- Discovery is intentionally **tech-focused** (`discovery_tech_only` in
  `app/config.py`) and **freshness-bounded** (`scan_max_age_days`, default 21).
- Only companies with a **known ATS** are scanned; `unknown` ones are skipped.
  Workday tenants and custom career sites (Apple, Meta, NVIDIA, Microsoft, Oracle,
  Intel, Tesla, TikTok, ByteDance, CrowdStrike) can't be resolved from a name and
  remain unscannable — resolving them needs following the careers-page redirect to
  discover the Workday `host|site` coordinate (not yet built).
- The browser agent must **never auto-submit** — it stops at the review step.
- LLM is configured via `backend/.env` (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`;
  currently OpenRouter). Discovery and scoring work without it; Prepare/agent need it.
- Commits go directly to `main` (solo repo). `pre-commit` runs gitleaks + hygiene hooks.

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
