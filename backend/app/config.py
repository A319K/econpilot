from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Job family classification keywords, checked in order against normalized job
# titles (and description as a fallback). First match wins; "other" is the
# default when nothing matches.
JOB_FAMILY_KEYWORDS: dict[str, list[str]] = {
    "ml": ["machine learning", "ml engineer", "mle", "ai engineer", "deep learning", "nlp", "computer vision"],
    "data": ["data engineer", "data scientist", "data analyst", "analytics engineer", "etl"],
    "cloud_infra": [
        "infrastructure",
        "platform engineer",
        "devops",
        "site reliability",
        "sre",
        "cloud engineer",
        "systems engineer",
    ],
    "swe": [
        "software engineer",
        "software developer",
        "swe",
        "backend",
        "frontend",
        "full stack",
        "full-stack",
        "web developer",
        "application developer",
        "forward deployed",
        "security engineer",
        "solutions engineer",
    ],
}

# Companies ranked by source reliability for dedup merges; higher index wins.
SOURCE_RANK: dict[str, int] = {
    "manual": 0,
    "github_repo": 1,
    "github_newgrad": 1,
    "ashby": 2,
    "lever": 2,
    "greenhouse": 2,
    "workday": 2,
}

# --- Phase 5 application agent (see app/agent/) ---------------------------
# These constants are the code-enforced half of the safety invariants. They
# live here, next to the other classification tables, so the exact wording is
# auditable in one place rather than scattered through the agent.

# Accessible click text that must NEVER be clicked - clicking any of these
# could submit the application. Matched case-insensitively as a substring
# (fuzzy) by app.agent.safety.is_blocklisted_click. The click helper checks
# EVERY click against this list, so a hijacked/confused LLM is physically
# unable to submit.
SUBMIT_BLOCKLIST: list[str] = [
    "submit application",
    "submit",
    "send application",
    "complete application",
    "finish",
]

# "apply now" is dangerous only as the *final* action - but it is also, on some
# sites, the button that opens the application form. It is blocked for every
# LLM-driven in-form click (the loop), and allowed ONLY for the adapter's
# deterministic entry click (get_apply_entry). Kept separate from
# SUBMIT_BLOCKLIST so the entry path can opt out without weakening the
# unconditional submit guard.
FINAL_ACTION_BLOCKLIST: list[str] = [
    "apply now",
]

# Field label/name/type fragments that must NEVER be filled. Matched
# case-insensitively as a substring by app.agent.safety.is_sensitive_field.
SENSITIVE_FIELD_PATTERNS: list[str] = [
    "password",
    "ssn",
    "social security",
    "salary expectation",
    "expected salary",
    "desired salary",
    "compensation expectation",
    "payment",
    "credit card",
    "card number",
    "cvv",
    "bank account",
    "routing number",
]

# Deterministic field-mapping synonyms: fragments found in a field's
# label/name/autocomplete -> the canonical profile concept the mapper resolves
# it to. Checked longest-first so multi-word fragments win over single words.
FIELD_SYNONYMS: dict[str, list[str]] = {
    "first_name": ["first name", "given name", "forename", "fname", "legal first"],
    "last_name": ["last name", "family name", "surname", "lname", "legal last"],
    "full_name": ["full name", "your name", "name", "candidate name", "applicant name"],
    "email": ["email", "e-mail"],
    "phone": ["phone", "mobile", "telephone", "cell", "contact number"],
    "address": ["street address", "address line", "address", "mailing address"],
    "city": ["city", "town", "locality"],
    "state": ["state", "province", "region"],
    "zip": ["zip", "postal code", "postcode"],
    "country": ["country"],
    "linkedin": ["linkedin"],
    "github": ["github"],
    "website": ["website", "portfolio", "personal site", "personal website"],
    "school": ["school", "university", "college", "institution"],
    "degree": ["degree"],
    "major": ["major", "field of study", "discipline", "concentration"],
    "gpa": ["gpa", "grade point"],
    "graduation_date": ["graduation date", "grad date", "expected graduation", "completion date"],
    "work_authorization": [
        "work authorization",
        "authorized to work",
        "legally authorized",
        "work eligibility",
        "employment authorization",
    ],
    "requires_sponsorship": [
        "sponsorship",
        "require sponsorship",
        "visa sponsorship",
        "need sponsorship",
    ],
    "willing_to_relocate": ["relocate", "relocation", "willing to move"],
    "gender": ["gender", "sex"],
    "ethnicity": ["ethnicity", "race", "hispanic", "latino"],
    "veteran": ["veteran", "protected veteran", "military"],
    "disability": ["disability", "disabled"],
    "resume": ["resume", "cv", "curriculum vitae"],
    "cover_letter": ["cover letter", "coverletter"],
}

# Options that count as "prefer not to answer" for EEO questions when the
# profile has no corresponding default. Matched case-insensitively as a
# substring against option labels.
DECLINE_OPTION_PATTERNS: list[str] = [
    "decline",
    "prefer not",
    "do not wish",
    "don't wish",
    "not to disclose",
    "not to answer",
    "i don't want to answer",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "z-ai/glm-5.2"
    llm_api_key: str = ""

    database_url: str = "sqlite:///./econpilot.db"

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    notifier: str = "none"
    hermes_send_target: str = "telegram"
    hermes_bin: str = "hermes"

    # Phase 6 watcher
    watcher_enabled: bool = False
    watch_interval_minutes: int = 30
    watch_notify_min_score: float = 40.0
    watch_quiet_hours: str | None = None

    # Phase B seasonal pre-activation: on the 1st of each month, refresh the
    # company corpus from the listings feed and flip companies expected to post
    # next month into active watch targets. Runs only when the watcher is on.
    seasonal_preactivation_enabled: bool = True

    # Discovery: GitHub internship-list repo (raw README table format).
    # Changes seasonally (verified live 2026-07-02), so kept fully configurable.
    github_repo_owner: str = "SimplifyJobs"
    github_repo_name: str = "Summer2026-Internships"
    github_repo_branch: str = "dev"
    # Structured listings feed (absolute date_posted, ATS urls, active flag) --
    # richer and more reliable than scraping the rendered README table.
    github_repo_listings_path: str = ".github/scripts/listings.json"
    # Additional listings feeds merged in alongside the primary one, for
    # redundancy and broader (incl. startup) coverage. Each entry is
    # "owner/name/branch/path" and must use the same listings.json schema. A
    # feed that fails to fetch is skipped, never failing the others.
    github_additional_feeds: list[str] = [
        "vanshb03/Summer2026-Internships/dev/.github/scripts/listings.json",
    ]
    # Discovery: GitHub new-grad (full-time) feeds. Same listings.json schema as
    # the internship feeds above, but every posting is a full-time new-grad role,
    # so they're fetched by a separate source (JobSource.github_newgrad) and
    # classified full_time -- never merged into the internship feeds. Used by
    # full-time scans alongside the ATS sweep.
    github_newgrad_feeds: list[str] = [
        "SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
    ]

    # Discovery: scoring
    preferred_job_families: list[str] = ["swe", "ml"]
    scan_concurrency: int = 8

    # Discovery: keep the queue tech-focused. Large ATS tenants (esp. Workday)
    # list every function -- retail, nursing, finance -- which floods the queue
    # with roles you'd never apply to. When True (default), full-time jobs that
    # classify to the "other" family are dropped at scan time. Every internship
    # is always kept (low volume, and intern titles often under-classify), as is
    # any full-time role in a tech family (swe/ml/data/cloud_infra). Set False to
    # ingest everything.
    discovery_tech_only: bool = True

    # Discovery: actively resolve unknown-ATS companies. Before each scan, probe
    # companies we know by name but not by ATS against the Greenhouse/Lever/Ashby
    # APIs and persist any hit, so names like Datadog/Palantir become directly
    # scannable instead of being silently skipped. Each company is probed once
    # per `ats_reprobe_after_days` window. Set False to disable auto-resolution.
    discovery_auto_resolve_ats: bool = True
    ats_reprobe_after_days: int = 30

    # Discovery: freshness. Jobs whose posted_at is older than this many days
    # (relative to the scan) are skipped at ingest time - internship boards
    # accumulate stale/closed roles, so a ~3-week window keeps the queue current.
    # Set to 0 to disable the cutoff. Jobs with no posted_at are always kept.
    scan_max_age_days: int = 21

    # Materials: LaTeX compilation and LLM-driven resume/cover-letter pipeline
    latex_compiler: str = "tectonic"
    output_dir: str = "output"
    jd_description_max_chars: int = 6000

    # Materials: whether Prepare rewrites a job-specific resume by default. When
    # False (the default), Prepare just selects the best-fit pre-built base
    # resume and reuses its already-compiled PDF - no per-job LLM rewrite or
    # LaTeX recompile. Per-job tailoring stays available by passing tailor=true
    # on a specific Prepare request. True restores tailor-every-time behavior.
    prepare_tailor_default: bool = False

    # Phase 5 application agent. The persistent user-data dir (relative to the
    # repo root) is gitignored; every cap below is a hard stop that PAUSEs the
    # run with a cap_exceeded reason when exceeded.
    agent_context_dir: str = "browser_contexts/default"
    agent_max_actions_per_step: int = 40
    agent_max_page_steps: int = 15
    agent_max_llm_calls: int = 25
    agent_wall_clock_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
