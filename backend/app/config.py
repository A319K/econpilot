from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Strong title phrases, checked in order. These families are deliberately broad:
# they select among a small library of resumes rather than trying to reproduce
# every employer's org chart. Generic titles such as "analyst" are handled by
# qualified domain signals in discovery.pipeline instead of matching alone.
JOB_FAMILY_KEYWORDS: dict[str, list[str]] = {
    "policy_research": [
        "economist",
        "economic analyst",
        "policy analyst",
        "economic research assistant",
        "economic research associate",
        "pre-doctoral",
        "predoctoral",
        "pre-doc",
        "predoc",
    ],
    "finance": [
        "investment banking",
        "investment analyst",
        "financial analyst",
        "finance analyst",
        "equity research",
        "credit research",
        "asset management",
        "portfolio analyst",
        "wealth management",
        "sales and trading",
        "sales & trading",
        "capital markets",
        "risk analyst",
        "treasury analyst",
        "valuation analyst",
        "fp&a",
    ],
    "consulting": [
        "economic consultant",
        "economic consulting",
        "management consultant",
        "strategy consultant",
        "consulting analyst",
        "consulting associate",
        "business consultant",
    ],
    "data_analytics": [
        "data analyst",
        "business analyst",
        "business intelligence",
        "analytics analyst",
        "quantitative analyst",
        "quant analyst",
        "quantitative researcher",
        "pricing analyst",
        "market research analyst",
        "product analyst",
        "operations analyst",
    ],
    "corporate": [
        "corporate finance",
        "corporate strategy",
        "strategy analyst",
        "commercial analyst",
        "business operations",
        "rotational program",
        "rotation program",
        "leadership development program",
    ],
}

# Description evidence used only when a title is generic (analyst, associate,
# research assistant, consultant, or intern). Requiring these signals prevents
# unrelated roles such as laboratory assistants and retail associates from
# entering the queue.
JOB_FAMILY_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "policy_research": [
        "econometrics",
        "microeconomics",
        "macroeconomics",
        "economic research",
        "public policy",
        "monetary policy",
        "federal reserve",
        "central bank",
        "causal inference",
    ],
    "finance": [
        "investment banking",
        "asset management",
        "capital markets",
        "equity research",
        "credit research",
        "financial modeling",
        "portfolio management",
        "mergers and acquisitions",
    ],
    "consulting": [
        "economic consulting",
        "management consulting",
        "client engagements",
        "case teams",
        "antitrust",
        "litigation support",
    ],
    "data_analytics": [
        "data analysis",
        "statistical analysis",
        "business intelligence",
        "predictive modeling",
        "sql",
        "tableau",
        "power bi",
    ],
    "corporate": [
        "corporate strategy",
        "business operations",
        "strategic planning",
        "leadership development",
        "rotational program",
        "commercial strategy",
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
    # Official first-party federal listing; wins over mirrors during dedup.
    "usajobs": 3,
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

    # Discovery: official USAJOBS Search API. The key is free but requires an
    # individual request to USAJOBS, so this remains an optional enhancement;
    # the keyless ATS and GitHub discovery loop works when both values are blank.
    usajobs_api_key: str = ""
    usajobs_user_agent: str = ""

    # Discovery: scoring
    preferred_job_families: list[str] = ["finance", "consulting", "policy_research"]
    scan_concurrency: int = 8

    # Large ATS tenants list every function. Keep only postings that classify to
    # an economics-oriented family by default, for both internships and
    # full-time roles. Set False to ingest unclassified roles as well.
    discovery_econ_only: bool = True

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
