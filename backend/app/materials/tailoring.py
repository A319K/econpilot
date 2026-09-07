import logging

from sqlalchemy.orm import Session

from app.llm.client import complete
from app.materials.latex import LatexError, build_output_name, compile_pdf, reject_dangerous_latex
from app.materials.prompts import TAILORING_SYSTEM, tailoring_user
from app.materials.regions import parse_regions, replace_region
from app.models.job import Job
from app.models.resume_version import ResumeVersion
from app.profile import get_profile

logger = logging.getLogger(__name__)


def _profile_skills() -> list[str]:
    profile = get_profile()
    return [*profile.skills.languages, *profile.skills.frameworks, *profile.skills.tools]


async def _tailor_region(name: str, content: str, keywords: dict, profile_skills: list[str]) -> str:
    """Return the LLM's rewrite of one region, or the original content if
    the LLM call fails or its output fails safety validation."""
    try:
        llm_output = await complete(
            TAILORING_SYSTEM, tailoring_user(name, content, keywords, profile_skills), max_tokens=2048
        )
        reject_dangerous_latex(llm_output)
        return llm_output
    except Exception:
        logger.warning("Tailoring failed for region %r; keeping original content", name)
        return content


def _build_source(base_source: str, region_overrides: dict[str, str]) -> str:
    source = base_source
    for name, content in region_overrides.items():
        source = replace_region(source, name, content)
    return source


async def tailor_resume(db: Session, base: ResumeVersion, job: Job, keywords: dict) -> ResumeVersion:
    """Produce a lightly-tailored child ResumeVersion of `base` for `job`.

    Falls back to returning `base` unchanged (no new row) if no region could
    be tailored, or if the tailored document never compiles.
    """
    regions = parse_regions(base.latex_source)
    profile_skills = _profile_skills()

    tailored_content = {
        name: await _tailor_region(name, content, keywords, profile_skills)
        for name, content in regions.items()
    }
    regions_changed = [name for name, content in tailored_content.items() if content != regions[name]]

    if not regions_changed:
        return base

    output_name = build_output_name(job.company.name, job.id, "resume")
    full_source = _build_source(base.latex_source, tailored_content)

    try:
        pdf_path = compile_pdf(full_source, output_name)
        final_source = full_source
    except LatexError:
        pdf_path = None
        final_source = None

        # Retry by reverting one previously-tailored region at a time until
        # a compilable combination is found (isolates "the failing region").
        for reverted_name in regions_changed:
            trial_overrides = dict(tailored_content)
            trial_overrides[reverted_name] = regions[reverted_name]
            trial_source = _build_source(base.latex_source, trial_overrides)
            try:
                pdf_path = compile_pdf(trial_source, output_name)
                final_source = trial_source
                break
            except LatexError:
                continue

        if pdf_path is None:
            logger.warning(
                "Tailored resume for job %s failed to compile after retry; "
                "falling back to the untailored base resume",
                job.id,
            )
            return base

    tailored = ResumeVersion(
        name=f"{base.name} (tailored for job {job.id})",
        job_family=base.job_family,
        latex_source=final_source,
        pdf_path=str(pdf_path),
        is_base_template=False,
        parent_id=base.id,
        keywords=base.keywords,
    )
    db.add(tailored)
    db.flush()
    return tailored
