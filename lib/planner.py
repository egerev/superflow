"""Plan parsing utilities — shared heading parser for planner and supervisor."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone


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


def _extract_sprint_section(lines: list, start_line: int, end_line: int) -> str:
    """Return the text slice for a sprint section."""
    return "\n".join(lines[start_line:end_line])


def plan_to_queue(plan_path: str, feature: str, base_branch: str = "feat", state_path: str | None = None) -> dict:
    """Parse a plan file and return a queue dict matching the queue schema.

    Raises ValueError for:
    - No sprints found
    - Duplicate sprint IDs
    - Dependency references to non-existent sprint IDs
    - Circular dependencies
    """
    # Normalize to relative path — absolute paths would be rejected by SprintQueue.load()
    if os.path.isabs(plan_path):
        try:
            plan_path = os.path.relpath(plan_path)
        except ValueError:
            pass  # On Windows cross-drive, relpath can fail; keep as-is

    with open(plan_path) as f:
        content = f.read()

    headings = _parse_sprint_headings(content)
    if not headings:
        raise ValueError(f"No sprint headings found in plan file: {plan_path}")

    lines = content.split("\n")

    # Check for duplicate IDs
    ids = [h["id"] for h in headings]
    seen = set()
    for sid in ids:
        if sid in seen:
            raise ValueError(f"Duplicate sprint ID: {sid}")
        seen.add(sid)

    id_set = set(ids)

    # Allow optional markdown bold markers (**) after the colon
    _complexity_re = re.compile(r'(?:complexity|Complexity):\s*\*?\*?\s*(\w+)', re.IGNORECASE)
    _depends_re = re.compile(
        r'(?:depends.on|Dependencies):\s*\*?\*?\s*(?:Sprint\s+)?(\d+(?:\s*,\s*(?:Sprint\s+)?\d+)*)',
        re.IGNORECASE,
    )

    sprints = []
    for h in headings:
        section = _extract_sprint_section(lines, h["start_line"], h["end_line"])

        # Extract complexity
        cm = _complexity_re.search(section)
        complexity = cm.group(1).lower() if cm else "medium"

        # Extract depends_on
        dm = _depends_re.search(section)
        if dm:
            raw = dm.group(1)
            parts = re.split(r'\s*,\s*', raw)
            depends_on = []
            for part in parts:
                # Strip optional "Sprint " prefix from each part
                part = re.sub(r'(?i)^sprint\s+', '', part.strip())
                if part:
                    depends_on.append(int(part))
        else:
            depends_on = []

        # Validate dependency references exist
        for dep in depends_on:
            if dep not in id_set:
                raise ValueError(
                    f"Sprint {h['id']} depends on Sprint {dep}, which does not exist"
                )

        sprints.append({
            "id": h["id"],
            "title": h["title"],
            "status": "pending",
            "complexity": complexity,
            "plan_file": f"{plan_path}#sprint-{h['id']}",
            "branch": f"{base_branch}/{feature}-sprint-{h['id']}",
            "depends_on": depends_on,
            "pr": None,
            "retries": 0,
            "max_retries": 2,
            "error_log": None,
        })

    # Topological sort check for circular dependencies
    _check_no_cycles(sprints)

    # Compute content hash
    content_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
    now = datetime.now(timezone.utc).isoformat()

    # Read metadata from .superflow-state.json if available
    metadata = {}
    _state_file = state_path or ".superflow-state.json"
    if os.path.exists(_state_file):
        try:
            with open(_state_file) as f:
                state_data = json.load(f)
            context = state_data.get("context", {})
            for key in ("brief_file", "spec_file", "charter_file", "governance_mode"):
                value = context.get(key)
                if value:
                    metadata[key] = value
        except (json.JSONDecodeError, OSError):
            pass

    result = {
        "feature": feature,
        "created": now,
        "generated_from": {
            "plan_file": plan_path,
            "content_hash": content_hash,
            "generated_at": now,
        },
        "sprints": sprints,
    }
    if metadata:
        result["metadata"] = metadata
    return result


def charter_to_queue(charter_text: str, feature: str, base_branch: str = "feat") -> dict:
    """Parse sprint breakdown from an Autonomy Charter body (light-mode path).

    Expects headings like: ## Sprint N: Title [complexity: X]
    The bracket complexity tag is optional; defaults to 'medium'.
    Dependencies use the same format as plan files: **Dependencies:** Sprint M

    Raises ValueError if no sprint headings found or circular dependencies detected.
    """
    # Strip YAML frontmatter if present
    body = charter_text
    if body.startswith("---"):
        end = body.find("---", 3)
        if end != -1:
            body = body[end + 3:].strip()

    # Parse sprint headings — supports bracket complexity tag
    bracket_re = re.compile(
        r'^##\s+Sprint\s+(\d+)\s*(?:[:—\-]\s*(.+?))\s*(?:\[complexity:\s*(\w+)\])?\s*$',
        re.MULTILINE,
    )
    lines = body.split('\n')
    headings = []

    for match in bracket_re.finditer(body):
        sprint_id = int(match.group(1))
        title = (match.group(2) or f"Sprint {sprint_id}").strip()
        complexity = (match.group(3) or "medium").lower()
        start_line = body[:match.start()].count('\n')
        headings.append({
            "id": sprint_id,
            "title": title,
            "start_line": start_line,
            "end_line": None,
            "complexity": complexity,
        })

    # Also try headings without complexity bracket (fallback)
    if not headings:
        plain_headings = _parse_sprint_headings(body)
        for h in plain_headings:
            h["complexity"] = "medium"
        headings = plain_headings

    if not headings:
        raise ValueError("No sprint headings found in charter body")

    # Fill end_line
    for i, h in enumerate(headings):
        if i + 1 < len(headings):
            h["end_line"] = headings[i + 1]["start_line"]
        else:
            h["end_line"] = len(lines)

    # Check for duplicate IDs
    ids = [h["id"] for h in headings]
    seen = set()
    for sid in ids:
        if sid in seen:
            raise ValueError(f"Duplicate sprint ID: {sid}")
        seen.add(sid)

    id_set = set(ids)

    _depends_re = re.compile(
        r'(?:depends.on|Dependencies):\s*\*?\*?\s*(?:Sprint\s+)?(\d+(?:\s*,\s*(?:Sprint\s+)?\d+)*)',
        re.IGNORECASE,
    )

    sprints = []
    for h in headings:
        section = _extract_sprint_section(lines, h["start_line"], h["end_line"])

        # Extract depends_on
        dm = _depends_re.search(section)
        if dm:
            raw = dm.group(1)
            parts = re.split(r'\s*,\s*', raw)
            depends_on = []
            for part in parts:
                part = re.sub(r'(?i)^sprint\s+', '', part.strip())
                if part:
                    depends_on.append(int(part))
        else:
            depends_on = []

        # Validate dependency references exist
        for dep in depends_on:
            if dep not in id_set:
                raise ValueError(
                    f"Sprint {h['id']} depends on Sprint {dep}, which does not exist"
                )

        sprints.append({
            "id": h["id"],
            "title": h["title"],
            "status": "pending",
            "complexity": h["complexity"],
            "branch": f"{base_branch}/{feature}-sprint-{h['id']}",
            "depends_on": depends_on,
            "pr": None,
            "retries": 0,
            "max_retries": 2,
            "error_log": None,
        })

    _check_no_cycles(sprints)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "feature": feature,
        "created": now,
        "sprints": sprints,
    }


def _check_no_cycles(sprints: list) -> None:
    """Kahn's algorithm topological sort — raises ValueError on cycle."""
    graph = {s["id"]: list(s["depends_on"]) for s in sprints}
    in_degree = {s["id"]: 0 for s in sprints}
    for deps in graph.values():
        for dep in deps:
            in_degree[dep] = in_degree.get(dep, 0)  # ensure key exists
    # Count incoming edges for each node
    in_degree = {sid: 0 for sid in graph}
    for sid, deps in graph.items():
        for dep in deps:
            # dep -> sid means sid has one more in-degree? No:
            # deps = what sid depends ON, so dep must come BEFORE sid
            # edge: dep -> sid, so sid gets +1 in-degree
            pass
    # Build adjacency: if sid depends on dep, then dep -> sid
    adjacency = {sid: [] for sid in graph}
    in_degree = {sid: 0 for sid in graph}
    for sid, deps in graph.items():
        for dep in deps:
            adjacency[dep].append(sid)
            in_degree[sid] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(graph):
        raise ValueError("Circular dependency detected in sprint dependencies")


def save_queue(queue_dict: dict, path: str) -> None:
    """Save queue dict to JSON file atomically."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(queue_dict, f, indent=2)
    os.replace(tmp_path, path)


def validate_queue_freshness(queue_path: str, plan_path: str) -> tuple:
    """Check if queue was generated from the current plan content.

    Returns (is_fresh: bool, reason: str).
    """
    with open(queue_path) as f:
        queue_data = json.load(f)

    generated_from = queue_data.get("generated_from")
    if not generated_from:
        return (False, "queue has no generated_from metadata")

    stored_hash = generated_from.get("content_hash", "")

    with open(plan_path) as f:
        current_content = f.read()
    current_hash = f"sha256:{hashlib.sha256(current_content.encode()).hexdigest()}"

    if stored_hash == current_hash:
        return (True, "")
    return (False, "plan modified since queue was generated")
