"""Named LLM prompt constants for the materials pipeline. Keeping these out
of the calling modules makes the exact wording auditable in one place -
important since job descriptions (untrusted input) flow into several of
these prompts."""

KEYWORD_EXTRACTION_SYSTEM = (
    "You extract structured keywords from a job description for resume "
    "tailoring. You do not invent requirements that aren't stated or "
    "strongly implied by the text."
)

KEYWORD_EXTRACTION_SCHEMA_HINT = (
    '{"skills": [string], "responsibilities": [string], '
    '"qualifications": [string], "nice_to_have": [string]}'
)


def keyword_extraction_user(title: str, description: str) -> str:
    return f"Job title: {title}\n\nJob description:\n{description}"


RESUME_SELECTION_SYSTEM = (
    "You select the best-matching resume template for a job from a short "
    "list of candidates. You only ever choose one of the given candidate "
    "ids - never invent a new one."
)

RESUME_SELECTION_SCHEMA_HINT = '{"resume_id": int, "reasoning": string}'


def resume_selection_user(title: str, keywords: dict, candidates: list[dict]) -> str:
    lines = [f"Job title: {title}", f"Extracted keywords: {keywords}", "Candidates:"]
    for c in candidates:
        lines.append(f"- id={c['id']} name={c['name']!r} keywords={c['keywords']}")
    lines.append("Return the id of the single best-matching candidate.")
    return "\n".join(lines)


TAILORING_SYSTEM = (
    "You lightly tailor one section of a resume to better match a job "
    "description, while following these hard rules without exception:\n"
    "1. You may ONLY reorder, rephrase, or re-emphasize content that is "
    "already present in the section below or in the candidate's profile.\n"
    "2. You must NEVER add a skill, technology, tool, or piece of "
    "experience that is not already present in the section or profile.\n"
    "3. Your output must be a valid LaTeX fragment of similar length to "
    "the original, using only standard formatting commands already in use "
    "(no \\input, \\include, \\write, \\immediate, or \\def).\n"
    "4. Return ONLY the replacement LaTeX fragment - no commentary, no "
    "markdown code fences."
)


def tailoring_user(region_name: str, region_content: str, keywords: dict, profile_skills: list[str]) -> str:
    return (
        f"Region: {region_name}\n\n"
        f"Current content:\n{region_content}\n\n"
        f"Job description keywords: {keywords}\n\n"
        f"Candidate's actual skills (from profile, for reference only - do "
        f"not add any not already in the region above): {profile_skills}"
    )


COVER_LETTER_SYSTEM = (
    "You write a professional, specific cover letter draft (250-350 words, "
    "plain text, no LaTeX). Hard rules:\n"
    "1. Never fabricate experience, skills, or accomplishments not present "
    "in the candidate profile provided.\n"
    "2. Avoid cliches such as 'I am writing to express my interest' or "
    "'I am excited to apply'.\n"
    "3. Be concrete: reference specific job requirements and specific "
    "profile experience/skills that match them.\n"
    "4. Return only the letter body text - no salutation boilerplate like "
    "'Dear Hiring Manager' is required unless it flows naturally, no "
    "commentary, no markdown."
)


def cover_letter_user(job_title: str, company_name: str, keywords: dict, profile_summary: str) -> str:
    return (
        f"Job title: {job_title}\n"
        f"Company: {company_name}\n"
        f"Extracted job keywords: {keywords}\n\n"
        f"Candidate profile summary:\n{profile_summary}"
    )
