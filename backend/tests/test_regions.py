import pytest

from app.materials.regions import parse_regions, replace_region

SAMPLE = """\\documentclass{article}
\\begin{document}
Intro text, untouchable.

%% TAILOR-BEGIN:summary
Original summary content.
Second line.
%% TAILOR-END:summary

Middle text, also untouchable.

%% TAILOR-BEGIN:skills
Python, TypeScript, FastAPI
%% TAILOR-END:skills

\\end{document}
"""


def test_parse_regions_extracts_all_named_regions():
    regions = parse_regions(SAMPLE)

    assert set(regions.keys()) == {"summary", "skills"}
    assert "Original summary content." in regions["summary"]
    assert "Second line." in regions["summary"]
    assert regions["skills"].strip() == "Python, TypeScript, FastAPI"


def test_parse_regions_returns_empty_dict_when_no_markers():
    assert parse_regions("\\documentclass{article}\n\\begin{document}\\end{document}") == {}


def test_replace_region_swaps_only_named_region_content():
    updated = replace_region(SAMPLE, "skills", "Go, Rust, Kubernetes\n")

    regions = parse_regions(updated)
    assert regions["skills"].strip() == "Go, Rust, Kubernetes"
    # The untouched region and surrounding document must be unaffected.
    assert regions["summary"] == parse_regions(SAMPLE)["summary"]
    assert "Intro text, untouchable." in updated
    assert "Middle text, also untouchable." in updated


def test_replace_region_preserves_marker_lines():
    updated = replace_region(SAMPLE, "summary", "New summary.\n")

    assert "%% TAILOR-BEGIN:summary" in updated
    assert "%% TAILOR-END:summary" in updated


def test_replace_region_raises_for_unknown_region():
    with pytest.raises(ValueError):
        replace_region(SAMPLE, "nonexistent", "content")


def test_replace_region_handles_content_with_backslashes():
    # Regression guard: naive re.sub(str) replacement would misinterpret
    # backslash sequences in new_content as backreferences.
    updated = replace_region(SAMPLE, "skills", "\\textbf{Python} \\& Rust\n")

    regions = parse_regions(updated)
    assert regions["skills"].strip() == "\\textbf{Python} \\& Rust"


def test_replace_region_does_not_mutate_other_same_prefix_region_names():
    source = (
        "%% TAILOR-BEGIN:skills\nA\n%% TAILOR-END:skills\n"
        "%% TAILOR-BEGIN:skills2\nB\n%% TAILOR-END:skills2\n"
    )
    updated = replace_region(source, "skills", "C\n")
    regions = parse_regions(updated)

    assert regions["skills"].strip() == "C"
    assert regions["skills2"].strip() == "B"


def test_round_trip_parse_and_replace_with_same_content_is_identity():
    regions = parse_regions(SAMPLE)
    updated = replace_region(SAMPLE, "summary", regions["summary"])
    assert updated == SAMPLE
