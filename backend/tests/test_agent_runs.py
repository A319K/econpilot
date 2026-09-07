"""Unit tests for the run-setup helpers in app.agent.runs that don't need a
browser: the per-company resume staging (upload as '<company>_resume.pdf')."""

from pathlib import Path

from app.agent import runs


def test_company_slug_normalizes_punctuation_and_spaces():
    assert runs._company_slug("Melius") == "melius"
    assert runs._company_slug("A&A Prep Inc.") == "a_a_prep_inc"
    assert runs._company_slug("  Stripe, Inc.  ") == "stripe_inc"
    # Degenerate names still yield a usable filename stem.
    assert runs._company_slug("!!!") == "company"


def test_stage_resume_copies_to_company_named_file(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "REPO_ROOT", tmp_path)
    src = tmp_path / "Resume.pdf"
    src.write_bytes(b"%PDF-1.4 fake")

    staged = runs._stage_resume_for_company(str(src), "Melius")

    assert staged is not None
    dest = Path(staged)
    assert dest.name == "melius_resume.pdf"
    assert dest.read_bytes() == b"%PDF-1.4 fake"
    # The canonical source is untouched.
    assert src.exists()


def test_stage_resume_passthrough_when_no_path():
    assert runs._stage_resume_for_company(None, "Melius") is None


def test_stage_resume_passthrough_when_source_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "REPO_ROOT", tmp_path)
    missing = str(tmp_path / "nope.pdf")
    # No copy possible -> return the original path unchanged (loop decides).
    assert runs._stage_resume_for_company(missing, "Melius") == missing
