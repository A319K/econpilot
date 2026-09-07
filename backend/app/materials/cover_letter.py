from pathlib import Path

from sqlalchemy.orm import Session

from app.llm.client import complete
from app.materials.latex import build_output_name, compile_pdf, escape_latex
from app.materials.prompts import COVER_LETTER_SYSTEM, cover_letter_user
from app.models.application import Application
from app.models.cover_letter import CoverLetter
from app.models.job import Job
from app.profile import Profile, get_profile

_LETTER_PREAMBLE = "\\documentclass[11pt]{article}\n\\usepackage[margin=1in]{geometry}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{1em}\n\\begin{document}\n"
_LETTER_POSTAMBLE = "\n\\end{document}\n"


def build_profile_summary(profile: Profile) -> str:
    lines = [f"Name: {profile.personal.name}"]

    if profile.education:
        edu = profile.education[0]
        lines.append(f"Education: {edu.degree} in {edu.major}, {edu.school}")

    for exp in profile.work_experience[:2]:
        lines.append(f"Experience: {exp.title} at {exp.company}")
        for bullet in exp.bullets[:3]:
            lines.append(f"  - {bullet}")

    skills = [*profile.skills.languages, *profile.skills.frameworks, *profile.skills.tools]
    if skills:
        lines.append(f"Skills: {', '.join(skills)}")

    return "\n".join(lines)


def render_letter_latex(content: str) -> str:
    """Wrap plain-text cover letter content in a minimal LaTeX letter doc,
    escaping special characters and preserving paragraph breaks."""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    escaped = "\n\n".join(escape_latex(p) for p in paragraphs)
    return _LETTER_PREAMBLE + escaped + _LETTER_POSTAMBLE


def compile_cover_letter(content: str, company_name: str, job_id: int) -> Path:
    output_name = build_output_name(company_name, job_id, "cover_letter")
    latex_source = render_letter_latex(content)
    return compile_pdf(latex_source, output_name, subdir="cover_letters")


async def generate_cover_letter(db: Session, application: Application, job: Job, keywords: dict) -> CoverLetter:
    profile = get_profile()
    profile_summary = build_profile_summary(profile)

    content = await complete(
        COVER_LETTER_SYSTEM,
        cover_letter_user(job.title, job.company.name, keywords, profile_summary),
        max_tokens=2048,
    )
    content = content.strip()

    pdf_path = compile_cover_letter(content, job.company.name, job.id)

    cover_letter = CoverLetter(
        application_id=application.id,
        content=content,
        pdf_path=str(pdf_path),
        needs_review=True,
    )
    db.add(cover_letter)
    db.flush()
    return cover_letter
