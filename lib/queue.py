"""Sprint queue with DAG-based resolution for autonomous execution."""
import json
import os


class SprintQueue:
    """Manages a queue of sprints with dependency tracking.

    Sprint dict fields:
        id, title, status, plan_file, branch, depends_on, pr, retries, max_retries, error_log
        Optional: tasks (list of task dicts for intra-sprint tracking)
    """

    def __init__(self, feature: str, created: str, sprints: list, baseline_cmd=None):
        self.feature = feature
        self.created = created
        self.sprints = sprints
        self.baseline_cmd = baseline_cmd

    @classmethod
    def load(cls, path: str) -> "SprintQueue":
        """Load a sprint queue from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(
            feature=data["feature"],
            created=data["created"],
            sprints=data["sprints"],
            baseline_cmd=data.get("baseline_cmd"),
        )

    def save(self, path: str) -> None:
        """Atomically save the queue to a JSON file (write .tmp + rename)."""
        data = {
            "feature": self.feature,
            "created": self.created,
            "baseline_cmd": self.baseline_cmd,
            "sprints": self.sprints,
        }
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp_path, path)

    def _find_sprint(self, sprint_id: int) -> dict:
        """Find sprint by ID or raise KeyError."""
        for s in self.sprints:
            if s["id"] == sprint_id:
                return s
        raise KeyError(f"Sprint {sprint_id} not found")

    def next_runnable(self, max_parallel: int) -> list:
        """Return pending sprints whose dependencies are all completed.

        DAG resolution: a sprint is runnable if status=pending and every
        sprint ID in depends_on has status=completed.
        """
        completed = {s["id"] for s in self.sprints if s["status"] == "completed"}
        runnable = []
        for s in self.sprints:
            if s["status"] != "pending":
                continue
            if all(dep in completed for dep in s["depends_on"]):
                runnable.append(s)
            if len(runnable) >= max_parallel:
                break
        return runnable

    def mark_in_progress(self, sprint_id: int) -> None:
        """Mark a sprint as in_progress."""
        self._find_sprint(sprint_id)["status"] = "in_progress"

    def mark_completed(self, sprint_id: int, pr_url: str) -> None:
        """Mark a sprint as completed with its PR URL."""
        sprint = self._find_sprint(sprint_id)
        sprint["status"] = "completed"
        sprint["pr"] = pr_url

    def mark_failed(self, sprint_id: int, error: str) -> None:
        """Mark a sprint as failed with an error message."""
        sprint = self._find_sprint(sprint_id)
        sprint["status"] = "failed"
        sprint["error_log"] = error

    def mark_skipped(self, sprint_id: int, reason: str = "") -> None:
        """Mark a sprint as skipped."""
        sprint = self._find_sprint(sprint_id)
        sprint["status"] = "skipped"
        sprint["error_log"] = reason

    def is_done(self) -> bool:
        """Check if all sprints are in terminal states (completed/failed/skipped)."""
        terminal = {"completed", "failed", "skipped"}
        return all(s["status"] in terminal for s in self.sprints)

    def summary(self) -> dict:
        """Return counts by status."""
        counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "skipped": 0}
        for s in self.sprints:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        return counts

    def skip_blocked_sprints(self) -> None:
        """Skip all pending sprints whose dependencies include a failed/skipped sprint.

        Handles transitive dependencies: if sprint 1 failed, sprint 2 depends on 1
        gets skipped, then sprint 3 depending on 2 also gets skipped.
        """
        changed = True
        while changed:
            changed = False
            blocked_ids = {
                s["id"] for s in self.sprints
                if s["status"] in ("failed", "skipped")
            }
            for s in self.sprints:
                if s["status"] != "pending":
                    continue
                if any(dep in blocked_ids for dep in s["depends_on"]):
                    s["status"] = "skipped"
                    s["error_log"] = "dependency failed"
                    changed = True
