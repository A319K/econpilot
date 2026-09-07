# Contributing to EconPilot

Thanks for taking a look. This is a local-first job-application automation tool;
contributions of new job sources, ATS adapters, and notification backends are
especially welcome.

## Development setup

Run the one-time setup script from the repo root:

```bash
python scripts/setup.py
```

It copies `.env.example` → `backend/.env` and `profile.example.yaml` →
`profile.yaml`, runs the DB migrations, and prints next steps. Then:

```bash
# backend
cd backend
uv venv .venv && uv pip install -e ".[dev]" --python .venv/bin/python
.venv/bin/uvicorn app.main:app --reload

# frontend
cd frontend
npm install && npm run dev
```

See the [README](README.md) for the full quickstart and configuration table.

## Secret scanning (please enable)

EconPilot handles an LLM API key, an optional Telegram bot token, and your
personal profile. Enable the pre-commit hooks so a secret can't be committed by
accident:

```bash
pip install pre-commit
pre-commit install                 # scans staged changes on every commit
pre-commit run --all-files         # one-off scan of the whole tree
```

The config lives in `.pre-commit-config.yaml` and runs `gitleaks` plus a few
hygiene hooks (large-file guard, private-key detector, YAML/JSON validation).

## Tests

The full suite must stay green and behavior-preserving.

```bash
# backend — no browser, no LLM, no LaTeX required
cd backend && .venv/bin/python -m pytest

# frontend
cd frontend && npm run test && npm run build
```

Two marker-gated test groups are environment-dependent and skipped unless their
tooling is present (CI skips them too):

- `-m latex` — needs a real LaTeX compiler (`tectonic`) on `PATH`.
- `-m agent` — needs the `agent` extra (`uv pip install -e '.[agent]'` +
  `playwright install chromium`).

## Adding a new job source

There's a dedicated guide: [docs/adding-a-source.md](docs/adding-a-source.md).
It covers the `JobSource` interface, the committed-fixture test pattern, and the
live-verification expectation.

## Conventions

- Backend: FastAPI + SQLAlchemy 2.0 + Pydantic v2. New DB columns/tables get an
  Alembic migration.
- Frontend: Vite + React + TypeScript + Tailwind v4, server state in
  `@tanstack/react-query`. `frontend/src/api/types.ts` mirrors backend schemas
  by hand — keep them in sync.
- Match the style of the surrounding code; keep changes focused.
