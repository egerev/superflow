"""Plan parsing utilities — shared heading parser for planner and supervisor."""
import re


def _parse_sprint_headings(content: str) -> list:
    """Parse sprint headings from markdown plan content.

    Supports multiple heading formats:
    - ## Sprint N: Title (colon separator)
    - ## Sprint N — Title (em-dash separator)
    - ## Sprint N - Title (hyphen separator)
    - ## Sprint N (no title)

    Returns list of dicts with keys: id, title, start_line, end_line
    Lines are 0-indexed.
    """
    pattern = re.compile(r'^##\s+Sprint\s+(\d+)\s*(?:[:—\-]\s*(.+))?$', re.MULTILINE)
    lines = content.split('\n')
    headings = []

    for match in pattern.finditer(content):
        sprint_id = int(match.group(1))
        title = (match.group(2) or f"Sprint {sprint_id}").strip()
        start_line = content[:match.start()].count('\n')
        headings.append({
            "id": sprint_id,
            "title": title,
            "start_line": start_line,
            "end_line": None,
        })

    # Fill end_line: each heading ends where the next one starts (or EOF)
    for i, h in enumerate(headings):
        if i + 1 < len(headings):
            h["end_line"] = headings[i + 1]["start_line"]
        else:
            h["end_line"] = len(lines)

    return headings
