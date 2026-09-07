import subprocess
from pathlib import Path

import pytest

from app.materials.latex import (
    LatexError,
    build_output_name,
    compile_pdf,
    escape_latex,
    reject_dangerous_latex,
    slugify,
)


def test_escape_latex_escapes_all_special_chars():
    result = escape_latex("A & B % C $ D # E _ F { G } H ~ I ^ J \\ K")

    assert result == (
        "A \\& B \\% C \\$ D \\# E \\_ F \\{ G \\} H "
        "\\textasciitilde{} I \\textasciicircum{} J \\textbackslash{} K"
    )


def test_escape_latex_does_not_double_escape_inserted_backslashes():
    # A naive implementation might re-scan its own output and mangle the
    # backslash it just inserted for "&".
    result = escape_latex("&")
    assert result == "\\&"
    assert "\\\\" not in result


def test_escape_latex_leaves_plain_text_untouched():
    assert escape_latex("Software Engineer Intern") == "Software Engineer Intern"


@pytest.mark.parametrize("command", ["\\input", "\\include", "\\write", "\\immediate", "\\def"])
def test_reject_dangerous_latex_raises_for_each_forbidden_command(command):
    with pytest.raises(LatexError):
        reject_dangerous_latex(f"Some text {command}{{evil}}")


def test_reject_dangerous_latex_allows_safe_commands():
    reject_dangerous_latex("\\textbf{Python} and \\textit{FastAPI}")


def test_slugify_produces_url_safe_lowercase():
    assert slugify("Acme Corp, Inc.") == "acme-corp-inc"


def test_slugify_handles_empty_string():
    assert slugify("") == "untitled"


def test_build_output_name_includes_company_job_id_and_kind():
    name = build_output_name("Acme Corp", 42, "resume")
    assert name.startswith("acme-corp_42_resume_")


def test_compile_pdf_raises_latex_error_when_compiler_missing(monkeypatch, tmp_path):
    from app.materials import latex as latex_module

    monkeypatch.setattr(latex_module, "REPO_ROOT", tmp_path)

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(latex_module.subprocess, "run", fake_run)

    with pytest.raises(LatexError):
        compile_pdf("\\documentclass{article}\\begin{document}x\\end{document}", "test-output")


def test_compile_pdf_raises_latex_error_on_nonzero_exit(monkeypatch, tmp_path):
    from app.materials import latex as latex_module

    monkeypatch.setattr(latex_module, "REPO_ROOT", tmp_path)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="! Undefined control sequence.")

    monkeypatch.setattr(latex_module.subprocess, "run", fake_run)

    with pytest.raises(LatexError, match="Undefined control sequence"):
        compile_pdf("\\bad{latex", "test-output")


def test_compile_pdf_copies_produced_pdf_to_output_dir(monkeypatch, tmp_path):
    from app.materials import latex as latex_module

    monkeypatch.setattr(latex_module, "REPO_ROOT", tmp_path)

    def fake_run(cmd, capture_output, text, timeout):
        outdir = Path(cmd[cmd.index("--outdir") + 1])
        (outdir / "document.pdf").write_bytes(b"%PDF-1.4 fake")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(latex_module.subprocess, "run", fake_run)

    dest = compile_pdf("\\documentclass{article}\\begin{document}x\\end{document}", "acme_1_resume", subdir="resumes")

    assert dest.exists()
    assert dest.name == "acme_1_resume.pdf"
    assert dest.parent == tmp_path / "output" / "resumes"


@pytest.mark.latex
def test_compile_pdf_real_tectonic_produces_valid_pdf(tmp_path, monkeypatch):
    from app.materials import latex as latex_module

    monkeypatch.setattr(latex_module, "REPO_ROOT", tmp_path)

    source = "\\documentclass{article}\n\\begin{document}\nHello, world.\n\\end{document}\n"
    dest = compile_pdf(source, "smoke-test")

    assert dest.exists()
    assert dest.read_bytes().startswith(b"%PDF")
