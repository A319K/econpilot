import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

COMPILE_TIMEOUT_SECONDS = 60
LOG_TAIL_CHARS = 4000


class LatexError(Exception):
    """Raised for compilation failures and prompt-injection-shaped LLM output."""


_LATEX_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_ESCAPE_RE = re.compile("|".join(re.escape(ch) for ch in _LATEX_ESCAPE_MAP))

# Commands that could let untrusted (JD-derived) text read/write files or
# redefine macros. A job description is untrusted input that flows into
# tailoring/cover-letter prompts, so any LLM output containing these is
# rejected outright rather than spliced into a document we compile.
_DANGEROUS_COMMANDS = (r"\input", r"\include", r"\write", r"\immediate", r"\def")


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text for safe embedding."""
    return _ESCAPE_RE.sub(lambda m: _LATEX_ESCAPE_MAP[m.group()], text)


def reject_dangerous_latex(text: str) -> None:
    """Raise LatexError if text contains a command with file/macro access."""
    for command in _DANGEROUS_COMMANDS:
        if command in text:
            raise LatexError(f"Rejected LLM output containing forbidden command: {command}")


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[\s_-]+", "-", value) or "untitled"


def build_output_name(company: str, job_id: int, kind: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(company)}_{job_id}_{kind}_{timestamp}"


def compile_pdf(latex_source: str, output_name: str, subdir: str = "resumes") -> Path:
    """Compile latex_source with the configured LaTeX compiler and copy the
    resulting PDF to output/<subdir>/<output_name>.pdf. Raises LatexError
    with the compiler log tail on failure."""
    settings = get_settings()
    output_root = REPO_ROOT / settings.output_dir / subdir
    output_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / "document.tex"
        tex_file.write_text(latex_source, encoding="utf-8")

        try:
            result = subprocess.run(
                [settings.latex_compiler, str(tex_file), "--outdir", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise LatexError(f"LaTeX compiler '{settings.latex_compiler}' not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise LatexError(f"LaTeX compilation timed out: {exc}") from exc

        if result.returncode != 0:
            log_tail = (result.stdout + "\n" + result.stderr)[-LOG_TAIL_CHARS:]
            raise LatexError(f"LaTeX compilation failed (exit {result.returncode}):\n{log_tail}")

        produced_pdf = tmp_path / "document.pdf"
        if not produced_pdf.exists():
            raise LatexError("LaTeX compiler reported success but no PDF was produced")

        dest = output_root / f"{output_name}.pdf"
        shutil.copyfile(produced_pdf, dest)
        return dest
