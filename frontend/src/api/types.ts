// Hand-written from backend/app/schemas/*.py and backend/app/models/*.py.
// Keep in sync manually - there is no codegen step.

export const ATS_TYPES = ["greenhouse", "lever", "ashby", "workday", "other", "unknown"] as const
export type AtsType = (typeof ATS_TYPES)[number]

export const JOB_SOURCES = [
  "greenhouse",
  "lever",
  "ashby",
  "workday",
  "github_repo",
  "github_newgrad",
  "manual",
] as const
export type JobSource = (typeof JOB_SOURCES)[number]

export const ROLE_TYPES = ["internship", "full_time"] as const
export type RoleType = (typeof ROLE_TYPES)[number]

export const JOB_FAMILIES = ["swe", "data", "cloud_infra", "ml", "other"] as const
export type JobFamily = (typeof JOB_FAMILIES)[number]

export const APPLICATION_STATUSES = [
  "discovered",
  "queued",
  "in_progress",
  "ready_to_submit",
  "submitted",
  "oa",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
] as const
export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number]

// Mirrors backend/app/tracking/state_machine.py ALLOWED_TRANSITIONS exactly.
export const ALLOWED_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  discovered: ["queued", "withdrawn"],
  queued: ["in_progress", "withdrawn"],
  in_progress: ["ready_to_submit", "queued", "withdrawn"],
  ready_to_submit: ["submitted", "in_progress", "withdrawn"],
  submitted: ["oa", "interview", "offer", "rejected", "withdrawn"],
  oa: ["interview", "offer", "rejected", "withdrawn"],
  interview: ["offer", "rejected", "withdrawn"],
  offer: [],
  rejected: [],
  withdrawn: [],
}

export interface Company {
  id: number
  name: string
  careers_url: string | null
  ats_type: AtsType
  ats_board_id: string | null
  is_target: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface CompanyCreate {
  name: string
  careers_url?: string | null
  ats_type?: AtsType
  ats_board_id?: string | null
  is_target?: boolean
  notes?: string | null
}

export interface CompanyUpdate {
  name?: string | null
  careers_url?: string | null
  ats_type?: AtsType | null
  ats_board_id?: string | null
  is_target?: boolean | null
  notes?: string | null
}

export interface Job {
  id: number
  company_id: number
  title: string
  location: string | null
  url: string
  source: JobSource
  role_type: RoleType
  job_family: JobFamily
  description: string | null
  posted_at: string | null
  discovered_at: string
  score: number
  score_breakdown: Record<string, unknown> | null
  is_active: boolean
  dedup_hash: string
  created_at: string
  updated_at: string
}

export interface ManualJobCreate {
  url: string
  title?: string | null
  company_name?: string | null
  role_type: RoleType
  notes?: string | null
}

export interface JobListParams {
  role_type?: RoleType
  job_family?: JobFamily
  min_score?: number
  source?: JobSource
  is_active?: boolean
  company_id?: number
  discovered_after?: string
  sort?: "score" | "recent"
  page?: number
  page_size?: number
}

export interface PrepareRequest {
  tailor?: boolean
  cover_letter?: boolean
}

export interface PrepareReport {
  resume_used: number
  tailored: boolean
  regions_changed: string[]
  cover_letter_id: number | null
  pdf_paths: Record<string, string>
  llm_calls_made: number
}

export interface ScanRequest {
  role_type?: "all" | RoleType
  targets_only?: boolean
}

export interface ScanReport {
  companies_scanned: number
  resolved_companies?: number
  jobs_found: number
  new: number
  duplicates: number
  errors: string[]
}

export interface ResumeVersion {
  id: number
  name: string
  job_family: JobFamily
  /** Null for a PDF the user uploaded — there is no source to compile. */
  latex_source: string | null
  pdf_path: string | null
  original_filename: string | null
  is_uploaded: boolean
  is_base_template: boolean
  parent_id: number | null
  keywords: unknown[] | null
  created_at: string
  updated_at: string
}

export interface ResumeVersionCreate {
  name: string
  job_family: JobFamily
  latex_source: string
  keywords?: string[]
}

export interface ResumeVersionUpdate {
  name?: string | null
  job_family?: JobFamily | null
  latex_source?: string | null
  keywords?: string[] | null
}

export interface CoverLetter {
  id: number
  application_id: number
  content: string
  pdf_path: string | null
  needs_review: boolean
  created_at: string
  updated_at: string
}

export interface CoverLetterUpdate {
  content: string
}

export interface CoverLetterReview {
  reviewed: boolean
}

export interface JobSummary {
  id: number
  title: string
  company_name: string
  url: string
  score: number
  role_type: RoleType
}

export interface ResumeVersionSummary {
  id: number
  name: string
  pdf_path: string | null
}

export interface CoverLetterSummary {
  id: number
  content: string
  needs_review: boolean
}

export interface StatusHistoryEntry {
  from: string
  to: string
  timestamp: string
  note: string | null
  forced?: true
}

export interface ApplicationListItem {
  id: number
  job_id: number
  status: ApplicationStatus
  resume_version_id: number | null
  cover_letter_id: number | null
  submitted_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
  job: JobSummary
}

export interface ApplicationDetail {
  id: number
  job_id: number
  status: ApplicationStatus
  submitted_at: string | null
  notes: string | null
  status_history: StatusHistoryEntry[] | null
  created_at: string
  updated_at: string
  job: Job
  resume_version: ResumeVersionSummary | null
  cover_letter: CoverLetterSummary | null
}

export interface StatusUpdate {
  status: ApplicationStatus
  note?: string | null
  force?: boolean
}

export interface NotesUpdate {
  notes?: string | null
}

export interface ApplicationListParams {
  status?: ApplicationStatus[]
  role_type?: RoleType
  company_id?: number
  has_cover_letter?: boolean
  submitted_after?: string
  submitted_before?: string
  page?: number
  page_size?: number
}

// Mirrors backend/app/models/agent_run.py.
export const AGENT_RUN_STATUSES = [
  "running",
  "paused",
  "ready_for_review",
  "failed",
  "abandoned",
] as const
export type AgentRunStatus = (typeof AGENT_RUN_STATUSES)[number]

export const PAUSE_REASONS = [
  "login_required",
  "captcha",
  "unmapped_required_field",
  "cap_exceeded",
  "error",
] as const
export type PauseReason = (typeof PAUSE_REASONS)[number]

// action_log entries are heterogeneous (field actions vs. control events);
// kept loose since the UI renders them as terminal lines.
export type AgentActionLogEntry = Record<string, unknown>

export interface AgentRun {
  id: number
  application_id: number
  status: AgentRunStatus
  pause_reason: PauseReason | null
  started_at: string
  ended_at: string | null
  action_log: AgentActionLogEntry[] | null
  llm_calls: number
  screenshots_dir: string | null
}

// Mirrors backend/app/models/answer_bank.py.
export const ANSWER_SOURCES = ["user", "llm"] as const
export type AnswerSource = (typeof ANSWER_SOURCES)[number]

export interface AnswerBankEntry {
  id: number
  question_norm: string
  question_raw: string
  answer: string
  source: AnswerSource
  approved: boolean
  times_used: number
  last_used_at: string | null
  created_at: string
  updated_at: string
}

export interface AnswerBankCreate {
  question: string
  answer: string
  approved?: boolean
}

export interface AnswerBankUpdate {
  answer?: string
  approved?: boolean
}

export interface DailyCount {
  date: string
  count: number
}

export interface FunnelStats {
  submitted: number
  oa: number
  interview: number
  offer: number
  conversion_rates: {
    submitted_to_oa: number
    oa_to_interview: number
    interview_to_offer: number
  }
}

export interface CompanyCount {
  company_id: number
  company_name: string
  count: number
}

export interface RoleTypeStats {
  counts_by_status: Record<ApplicationStatus, number>
  submitted_per_day: DailyCount[]
  funnel: FunnelStats
  avg_hours_to_submit: number | null
  top_companies: CompanyCount[]
}

export interface StatsResponse {
  internship: RoleTypeStats
  full_time: RoleTypeStats
  all: RoleTypeStats
}

export interface HealthResponse {
  status: string
  db: "ok" | "fail"
}

export interface CycleSummary {
  started: string
  finished: string | null
  companies: number
  new_jobs: number
  deactivated: number
  notified: number
  errors: string[]
}

export interface WatcherStatus {
  enabled: boolean
  running: boolean
  last_cycle: CycleSummary | null
  next_run_at: string | null
}

export interface NotifyTestResult {
  success: boolean
  adapter: string
}

// --- profile (backend/app/schemas/profile.py + backend/app/profile.py) ------

export interface ProfilePersonal {
  name: string
  email: string
  phone: string
  city: string
  state: string
  address: string | null
  zip: string | null
  country: string | null
  linkedin: string | null
  github: string | null
  website: string | null
}

export interface ProfileEducation {
  school: string
  degree: string
  major: string
  gpa: number | null
  start: string
  end: string
}

export interface ProfileWorkExperience {
  company: string
  title: string
  start: string
  end: string
  bullets: string[]
}

export interface ProfileProject {
  name: string
  description: string | null
  bullets: string[]
  url: string | null
}

export interface ProfileSkills {
  languages: string[]
  frameworks: string[]
  tools: string[]
}

export interface ProfileEeoDefaults {
  gender: string | null
  ethnicity: string | null
  veteran: string | null
  disability: string | null
}

export interface ProfileStandardAnswers {
  work_authorization: string
  requires_sponsorship: boolean
  willing_to_relocate: boolean
  graduation_date: string
}

/** The editable document. `PUT /profile` replaces the whole thing. */
export interface ProfileWrite {
  personal: ProfilePersonal
  education: ProfileEducation[]
  work_experience: ProfileWorkExperience[]
  projects: ProfileProject[]
  skills: ProfileSkills
  eeo_defaults: ProfileEeoDefaults
  standard_answers: ProfileStandardAnswers
}

export interface Profile extends ProfileWrite {
  /** True while profile.yaml is absent and the bundled example stands in. */
  is_placeholder: boolean
}
