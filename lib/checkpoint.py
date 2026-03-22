"""Checkpoint save/load system for sprint execution state."""
import json
import os
import re


def save_checkpoint(checkpoints_dir: str, sprint_id: int, data: dict) -> None:
    """Save checkpoint data as JSON to sprint-{id}.json, creating dir if needed."""
    os.makedirs(checkpoints_dir, exist_ok=True)
    path = os.path.join(checkpoints_dir, f"sprint-{sprint_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_checkpoint(checkpoints_dir: str, sprint_id: int) -> dict | None:
    """Load checkpoint for a sprint. Returns None if file doesn't exist."""
    path = os.path.join(checkpoints_dir, f"sprint-{sprint_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_all_checkpoints(checkpoints_dir: str) -> list[dict]:
    """Load all checkpoint files (sprint-*.json) from the directory."""
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
