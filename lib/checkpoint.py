"""Checkpoint save/load system for sprint execution state."""
import json
import os
import re


def save_checkpoint(checkpoints_dir: str, sprint_id: int | str, data: dict) -> None:
    """Save checkpoint data as JSON to sprint-{id}.json, creating dir if needed."""
    os.makedirs(checkpoints_dir, exist_ok=True)
    path = os.path.join(checkpoints_dir, f"sprint-{sprint_id}.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.rename(tmp_path, path)


def load_checkpoint(checkpoints_dir: str, sprint_id: int | str) -> dict | None:
    """Load checkpoint for a sprint. Returns None if file doesn't exist."""
    path = os.path.join(checkpoints_dir, f"sprint-{sprint_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_checkpoint_by_name(checkpoints_dir: str, name: str) -> dict | None:
    """Load checkpoint by name. Loads sprint-{name}.json. Returns None if missing."""
    path = os.path.join(checkpoints_dir, f"sprint-{name}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_all_checkpoints(checkpoints_dir: str) -> list[dict]:
    """Load all sprint checkpoint files (sprint-{N}.json) from the directory.

    Only loads numeric-ID checkpoints (sprint-1.json, sprint-2.json, etc.).
    Named checkpoints (sprint-holistic.json) are excluded to avoid breaking
    downstream consumers that assume cp["sprint_id"] exists.
    Use load_checkpoint_by_name() for named checkpoints.
    """
    if not os.path.isdir(checkpoints_dir):
        return []
    results = []
    pattern = re.compile(r"^sprint-\d+\.json$")
    for fname in sorted(os.listdir(checkpoints_dir)):
        if pattern.match(fname):
            path = os.path.join(checkpoints_dir, fname)
            with open(path) as f:
                results.append(json.load(f))
    return results
