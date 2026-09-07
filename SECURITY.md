# Security & Privacy

EconPilot is a **local-first** tool. It runs on your machine, stores its data on
your machine, and is designed so that the only thing that ever leaves your
computer is what you deliberately send to the LLM provider you configured.

## What is stored locally

| Data | Location | Notes |
|------|----------|-------|
| Your personal profile | `profile.yaml` (repo root) | Name, contact info, education, work history, EEO self-identification. **Gitignored.** |
| LLM API key + notifier secrets | `backend/.env` | LLM key, optional Telegram bot token / chat id. **Gitignored.** |
| Application database | `backend/econpilot.db` (SQLite) | Jobs, companies, applications, generated cover letters, agent run logs. **Gitignored.** |
| Generated documents | `backend/output/` | Compiled resume/cover-letter PDFs. **Gitignored.** |
| Browser sessions | `backend/browser_contexts/` | The agent's persistent Chromium profile — **contains logged-in cookies** for any ATS you signed into during a run. **Gitignored.** Treat this directory like a password store. |

None of these are ever committed; `.gitignore` covers all of them, and a
gitleaks pre-commit hook (see `CONTRIBUTING.md`) guards against accidents.

## The one external data flow

There is exactly one outbound flow of personal/job data: the **materials
pipeline** and the **agent's answer generation** send text to the LLM endpoint
you configure (`LLM_BASE_URL`, default OpenRouter). Specifically:

- **Job description text** (truncated to `JD_DESCRIPTION_MAX_CHARS`) for keyword
  extraction, resume tailoring, and cover-letter drafting.
- **Profile excerpts** (a summary built from `profile.yaml`) so tailored
  materials and answers are grounded in your real background.
- **Custom application questions** the agent can't answer deterministically.

Choose an LLM provider you trust with that data. If you need everything to stay
on-device, point `LLM_BASE_URL` at a local inference server (e.g. an
OpenAI-compatible endpoint on `localhost`) — nothing else in EconPilot assumes a
specific provider.

The **watcher** and the **notification adapters** make no LLM calls. Telegram
notifications send job titles/companies/URLs to Telegram's Bot API; the
`hermes` adapter shells out to a local binary (never a shell, so untrusted
job-title text can't be used for command injection).

## The application agent's safety model

The agent that fills out application forms is **semi-autonomous and
human-supervised**, with safety enforced in code rather than only in prompts:

- **It never submits.** Every click is checked against a submit blocklist in the
  browser helper itself and refused — a confused or hijacked LLM is physically
  unable to click submit.
- **It never handles credentials.** Login walls, signup forms, and CAPTCHAs
  pause the run for you to resolve in the open browser.
- **It never fabricates.** Unmapped required fields and EEO questions without a
  configured default pause instead of guessing; EEO answers come only from
  `profile.eeo_defaults`.
- **Sensitive fields** (password, SSN, salary expectation, payment) are never
  filled.

See the README's "Application agent" section for the full model.

## Reporting a vulnerability

This is a personal/educational project without a formal disclosure process. If
you find a security issue, please open a GitHub issue describing it (omit any
real secrets or personal data from the report).
