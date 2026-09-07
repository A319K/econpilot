import re

# Base resume templates mark rewritable spans with paired comment markers:
#   %% TAILOR-BEGIN:skills
#   ...content the LLM may rewrite...
#   %% TAILOR-END:skills
# Everything outside these spans is untouchable by construction: tailoring
# only ever extracts and re-splices the text between a matching begin/end
# pair, never the document as a whole.
_REGION_RE = re.compile(
    r"%%\s*TAILOR-BEGIN:(?P<name>[\w-]+)\s*\n(?P<content>.*?)%%\s*TAILOR-END:(?P=name)",
    re.DOTALL,
)


def parse_regions(source: str) -> dict[str, str]:
    """Extract {region_name: content} for every TAILOR-BEGIN/END pair."""
    return {m.group("name"): m.group("content") for m in _REGION_RE.finditer(source)}


def replace_region(source: str, name: str, new_content: str) -> str:
    """Return source with the named region's content replaced.

    The BEGIN/END marker lines themselves are preserved untouched; only the
    text between them is swapped.
    """
    pattern = re.compile(
        rf"(%%\s*TAILOR-BEGIN:{re.escape(name)}\s*\n).*?(%%\s*TAILOR-END:{re.escape(name)})",
        re.DOTALL,
    )
    if not pattern.search(source):
        raise ValueError(f"Region '{name}' not found in source")

    return pattern.sub(lambda m: m.group(1) + new_content + m.group(2), source, count=1)
