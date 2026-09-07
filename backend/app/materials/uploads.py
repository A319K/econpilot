"""Storing resume PDFs the user uploads.

EconPilot's users are not developers: their resume is a finished PDF, not a
LaTeX template. This module accepts that file and puts it where the rest of the
pipeline already looks for compiled PDFs, so an uploaded resume and a compiled
one are interchangeable downstream.
"""

from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings
from app.materials.latex import REPO_ROOT, slugify

# A resume is a handful of pages; anything larger is a mistake or an attack.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_CHUNK = 64 * 1024

# Every PDF starts with this. Checked so a renamed .docx or .exe can't be
# stored and later handed to a browser as a resume.
_PDF_MAGIC = b"%PDF-"


class UploadError(Exception):
    """Raised for a file we won't accept, with a message safe to show a user."""


async def save_resume_pdf(upload: UploadFile, display_name: str, resume_id: int) -> Path:
    """Stream `upload` to output/resumes/ and return the stored path.

    The stored filename is generated from the resume's name and id — the
    client-supplied filename is never used to build a path, so a name like
    "../../.env" can't escape the output directory.
    """
    settings = get_settings()
    output_root = REPO_ROOT / settings.output_dir / "resumes"
    output_root.mkdir(parents=True, exist_ok=True)

    target = output_root / f"{slugify(display_name)}_{resume_id}_upload.pdf"

    size = 0
    first_chunk = True
    await upload.seek(0)
    try:
        with target.open("wb") as out:
            while chunk := await upload.read(_CHUNK):
                if first_chunk:
                    if not chunk.startswith(_PDF_MAGIC):
                        raise UploadError("That file isn't a PDF. Export your resume as a PDF and try again.")
                    first_chunk = False
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise UploadError("That file is larger than 10 MB. Resumes should be well under that.")
                out.write(chunk)
    except UploadError:
        target.unlink(missing_ok=True)
        raise

    if size == 0:
        target.unlink(missing_ok=True)
        raise UploadError("That file is empty.")

    return target


def safe_original_name(filename: str | None) -> str | None:
    """Keep the user's filename for display only — stripped of any path parts."""
    if not filename:
        return None
    return Path(filename).name[:255]
