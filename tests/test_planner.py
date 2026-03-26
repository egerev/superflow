"""Tests for lib/planner.py — sprint heading parser, plan extraction, queue generation."""
import hashlib
import json
import os
import tempfile
import unittest

from lib.planner import _parse_sprint_headings, _extract_plan_section, plan_to_queue, charter_to_queue, save_queue, validate_queue_freshness


class TestParseSprintHeadings(unittest.TestCase):
    def test_colon_separator(self):
        content = "## Sprint 1: My Title\nsome content\n## Sprint 2: Next"
        result = _parse_sprint_headings(content)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["title"], "My Title")

    def test_em_dash_separator(self):
        content = "## Sprint 1 — Em Dash Title\ncontent"
        result = _parse_sprint_headings(content)
        self.assertEqual(result[0]["title"], "Em Dash Title")

    def test_hyphen_separator(self):
        content = "## Sprint 1 - Hyphen Title\ncontent"
        result = _parse_sprint_headings(content)
        self.assertEqual(result[0]["title"], "Hyphen Title")

    def test_no_title(self):
        content = "## Sprint 3\ncontent"
        result = _parse_sprint_headings(content)
        self.assertEqual(result[0]["id"], 3)
        self.assertEqual(result[0]["title"], "Sprint 3")

    def test_start_line_zero_indexed(self):
        content = "# Plan\n\n## Sprint 1: Title\ncontent"
        result = _parse_sprint_headings(content)
        self.assertEqual(result[0]["start_line"], 2)

    def test_end_line_points_to_next_sprint(self):
        content = "## Sprint 1: First\ncontent\n## Sprint 2: Second\nmore"
        result = _parse_sprint_headings(content)
        self.assertEqual(result[0]["end_line"], 2)  # line index of "## Sprint 2"
        self.assertEqual(result[1]["start_line"], 2)

    def test_last_sprint_end_line_is_eof(self):
        content = "## Sprint 1: Only\nline1\nline2"
        result = _parse_sprint_headings(content)
        self.assertEqual(result[0]["end_line"], 3)  # total line count

    def test_empty_content(self):
        result = _parse_sprint_headings("")
        self.assertEqual(result, [])

    def test_no_sprint_headings(self):
        content = "# Overview\n## Background\nno sprints here"
        result = _parse_sprint_headings(content)
        self.assertEqual(result, [])

    def test_keys_present(self):
        content = "## Sprint 1: Title"
        result = _parse_sprint_headings(content)
        self.assertIn("id", result[0])
        self.assertIn("title", result[0])
        self.assertIn("start_line", result[0])
        self.assertIn("end_line", result[0])

    def test_sprint_id_is_int(self):
        content = "## Sprint 42: Big Number"
        result = _parse_sprint_headings(content)
        self.assertIsInstance(result[0]["id"], int)
        self.assertEqual(result[0]["id"], 42)


class TestExtractPlanSectionSprintPath(unittest.TestCase):
    """Verify _extract_plan_section uses _parse_sprint_headings for sprint fragments."""

    PLAN = (
        "# Plan\n\n"
        "## Sprint 1: Setup\nSetup tasks\n\n"
        "## Sprint 2 — Feature\nFeature tasks\n\n"
        "## Sprint 3 - Deploy\nDeploy tasks\n"
    )

    def test_sprint_fragment_colon_format(self):
        result = _extract_plan_section(self.PLAN, "sprint-1")
        self.assertIn("## Sprint 1: Setup", result)
        self.assertIn("Setup tasks", result)
        self.assertNotIn("Feature tasks", result)

    def test_sprint_fragment_em_dash_format(self):
        result = _extract_plan_section(self.PLAN, "sprint-2")
        self.assertIn("## Sprint 2", result)
        self.assertIn("Feature tasks", result)
        self.assertNotIn("Setup tasks", result)

    def test_sprint_fragment_last_sprint(self):
        result = _extract_plan_section(self.PLAN, "sprint-3")
        self.assertIn("## Sprint 3", result)
        self.assertIn("Deploy tasks", result)
        self.assertNotIn("Feature tasks", result)

    def test_sprint_fragment_not_found_returns_full_content(self):
        result = _extract_plan_section(self.PLAN, "sprint-99")
        self.assertEqual(result, self.PLAN)

    def test_non_sprint_fragment_still_works(self):
        content = "## Overview\nsome overview\n## Background\nsome background"
        result = _extract_plan_section(content, "overview")
        self.assertIn("## Overview", result)
        self.assertNotIn("Background", result)


# --- Shared plan content for plan_to_queue tests ---
_SAMPLE_PLAN = """\
## Sprint 1: Security Hardening

**Complexity:** medium
**Dependencies:** none

Some security tasks.

## Sprint 2 — Feature Build

**Complexity:** complex
**Dependencies:** Sprint 1

Building the feature.

## Sprint 3 - Final Polish

**Complexity:** simple
**Dependencies:** Sprint 1, Sprint 2

Polish.

## Sprint 4

No complexity or deps specified.
"""


def _write_plan(content=None):
    """Write plan content to a temp file, return (path, file_obj)."""
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    tf.write(content or _SAMPLE_PLAN)
    tf.flush()
    tf.close()
    return tf.name


class TestPlanToQueue(unittest.TestCase):
    def setUp(self):
        self.plan_path = _write_plan()

    def tearDown(self):
        if os.path.exists(self.plan_path):
            os.unlink(self.plan_path)

    def test_returns_dict_with_expected_keys(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        self.assertIn("feature", result)
        self.assertIn("created", result)
        self.assertIn("generated_from", result)
        self.assertIn("sprints", result)

    def test_feature_name_set(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        self.assertEqual(result["feature"], "my-feature")

    def test_four_sprints_parsed(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        self.assertEqual(len(result["sprints"]), 4)

    def test_sprint_titles_extracted(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        titles = [s["title"] for s in result["sprints"]]
        self.assertIn("Security Hardening", titles)
        self.assertIn("Feature Build", titles)
        self.assertIn("Final Polish", titles)
        self.assertIn("Sprint 4", titles)

    def test_complexity_extracted(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["complexity"], "medium")
        self.assertEqual(sprints[2]["complexity"], "complex")
        self.assertEqual(sprints[3]["complexity"], "simple")

    def test_complexity_default_when_missing(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[4]["complexity"], "medium")

    def test_depends_on_extracted(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[2]["depends_on"], [1])
        self.assertEqual(sprints[3]["depends_on"], [1, 2])

    def test_depends_on_default_empty_when_none(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["depends_on"], [])
        self.assertEqual(sprints[4]["depends_on"], [])

    def test_branch_name_uses_base_branch_and_feature(self):
        result = plan_to_queue(self.plan_path, "my-feature", base_branch="feat")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["branch"], "feat/my-feature-sprint-1")
        self.assertEqual(sprints[2]["branch"], "feat/my-feature-sprint-2")

    def test_plan_file_fragment(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        # plan_path is normalized to relative by plan_to_queue
        rel_path = os.path.relpath(self.plan_path)
        self.assertEqual(sprints[1]["plan_file"], f"{rel_path}#sprint-1")
        self.assertEqual(sprints[2]["plan_file"], f"{rel_path}#sprint-2")

    def test_sprint_status_is_pending(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        for s in result["sprints"]:
            self.assertEqual(s["status"], "pending")

    def test_sprint_fields_complete(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        sprint = result["sprints"][0]
        for key in ("id", "title", "status", "complexity", "plan_file", "branch",
                    "depends_on", "pr", "retries", "max_retries", "error_log"):
            self.assertIn(key, sprint)
        self.assertIsNone(sprint["pr"])
        self.assertEqual(sprint["retries"], 0)
        self.assertEqual(sprint["max_retries"], 2)
        self.assertIsNone(sprint["error_log"])

    def test_content_hash_in_generated_from(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        gf = result["generated_from"]
        self.assertIn("content_hash", gf)
        self.assertTrue(gf["content_hash"].startswith("sha256:"))

    def test_content_hash_matches_plan_file(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        with open(self.plan_path) as f:
            content = f.read()
        expected = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
        self.assertEqual(result["generated_from"]["content_hash"], expected)

    def test_generated_from_plan_file_path(self):
        result = plan_to_queue(self.plan_path, "my-feature")
        rel_path = os.path.relpath(self.plan_path)
        self.assertEqual(result["generated_from"]["plan_file"], rel_path)

    def test_reject_duplicate_sprint_ids(self):
        plan = "## Sprint 1: First\ncontent\n## Sprint 1: Duplicate\ncontent"
        path = _write_plan(plan)
        try:
            with self.assertRaises(ValueError):
                plan_to_queue(path, "feat")
        finally:
            os.unlink(path)

    def test_reject_missing_dependency(self):
        plan = "## Sprint 1: First\n**Dependencies:** Sprint 99\ncontent"
        path = _write_plan(plan)
        try:
            with self.assertRaises(ValueError):
                plan_to_queue(path, "feat")
        finally:
            os.unlink(path)

    def test_reject_circular_dependency(self):
        plan = (
            "## Sprint 1: First\n**Dependencies:** Sprint 2\ncontent\n"
            "## Sprint 2: Second\n**Dependencies:** Sprint 1\ncontent"
        )
        path = _write_plan(plan)
        try:
            with self.assertRaises(ValueError):
                plan_to_queue(path, "feat")
        finally:
            os.unlink(path)

    def test_reject_empty_plan(self):
        path = _write_plan("# No sprints here\nJust some text.")
        try:
            with self.assertRaises(ValueError):
                plan_to_queue(path, "feat")
        finally:
            os.unlink(path)

    def test_custom_base_branch(self):
        result = plan_to_queue(self.plan_path, "my-feat", base_branch="feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["branch"], "feature/my-feat-sprint-1")


class TestSaveQueue(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "queue.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_save_writes_valid_json(self):
        plan_path = _write_plan()
        try:
            q = plan_to_queue(plan_path, "feat")
            save_queue(q, self.path)
            with open(self.path) as f:
                data = json.load(f)
            self.assertEqual(data["feature"], "feat")
            self.assertEqual(len(data["sprints"]), 4)
        finally:
            os.unlink(plan_path)

    def test_save_is_atomic_no_tmp_left(self):
        plan_path = _write_plan()
        try:
            q = plan_to_queue(plan_path, "feat")
            save_queue(q, self.path)
            self.assertFalse(os.path.exists(self.path + ".tmp"))
        finally:
            os.unlink(plan_path)


class TestValidateQueueFreshness(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.plan_path = _write_plan()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)
        if os.path.exists(self.plan_path):
            os.unlink(self.plan_path)

    def _save_queue_from_plan(self):
        q = plan_to_queue(self.plan_path, "feat")
        save_queue(q, self.queue_path)

    def test_fresh_queue_returns_true(self):
        self._save_queue_from_plan()
        is_fresh, reason = validate_queue_freshness(self.queue_path, self.plan_path)
        self.assertTrue(is_fresh)
        self.assertEqual(reason, "")

    def test_modified_plan_returns_false(self):
        self._save_queue_from_plan()
        with open(self.plan_path, "a") as f:
            f.write("\n## Sprint 5: Extra\ncontent")
        is_fresh, reason = validate_queue_freshness(self.queue_path, self.plan_path)
        self.assertFalse(is_fresh)
        self.assertIn("plan modified", reason)

    def test_missing_generated_from_returns_false(self):
        # Write a queue without generated_from metadata
        data = {
            "feature": "feat",
            "created": "2026-01-01T00:00:00Z",
            "sprints": [],
        }
        with open(self.queue_path, "w") as f:
            json.dump(data, f)
        is_fresh, reason = validate_queue_freshness(self.queue_path, self.plan_path)
        self.assertFalse(is_fresh)
        self.assertIn("no generated_from", reason)


class TestSprintQueueGeneratedFrom(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "queue.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _make_queue_data(self, generated_from=None):
        data = {
            "feature": "test-feature",
            "created": "2026-03-23T12:00:00Z",
            "sprints": [
                {
                    "id": 1, "title": "First sprint", "status": "pending",
                    "plan_file": "docs/plan.md#sprint-1",
                    "branch": "feat/test-sprint-1", "depends_on": [],
                    "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
                }
            ],
        }
        if generated_from is not None:
            data["generated_from"] = generated_from
        return data

    def test_load_save_roundtrip_preserves_generated_from(self):
        from lib.queue import SprintQueue
        gf = {
            "plan_file": "docs/plan.md",
            "content_hash": "sha256:abc123",
            "generated_at": "2026-03-25T00:00:00Z",
        }
        data = self._make_queue_data(generated_from=gf)
        with open(self.path, "w") as f:
            json.dump(data, f)

        q = SprintQueue.load(self.path)
        self.assertEqual(q.generated_from, gf)

        q.save(self.path)
        with open(self.path) as f:
            reloaded = json.load(f)
        self.assertEqual(reloaded["generated_from"], gf)

    def test_old_format_without_generated_from_loads_fine(self):
        from lib.queue import SprintQueue
        data = self._make_queue_data()  # no generated_from
        with open(self.path, "w") as f:
            json.dump(data, f)

        q = SprintQueue.load(self.path)
        self.assertIsNone(q.generated_from)

    def test_save_without_generated_from_does_not_add_key(self):
        from lib.queue import SprintQueue
        data = self._make_queue_data()
        with open(self.path, "w") as f:
            json.dump(data, f)

        q = SprintQueue.load(self.path)
        q.save(self.path)
        with open(self.path) as f:
            reloaded = json.load(f)
        self.assertNotIn("generated_from", reloaded)


class TestPlanToQueueStateMetadata(unittest.TestCase):
    """Sprint 3: plan_to_queue() reads .superflow-state.json and populates queue metadata."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.plan_path = os.path.join(self.tmpdir, "plan.md")
        with open(self.plan_path, "w") as f:
            f.write("## Sprint 1: Test\nDo stuff.\n")
        self.state_path = os.path.join(self.tmpdir, ".superflow-state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_state(self, context: dict):
        state = {
            "version": 1,
            "phase": 2,
            "stage": "execution",
            "stage_index": 0,
            "last_updated": "2026-03-26T00:00:00Z",
            "context": context,
        }
        with open(self.state_path, "w") as f:
            json.dump(state, f)

    def test_brief_file_stored_in_queue_metadata(self):
        """plan_to_queue reads brief_file from state context and stores in metadata."""
        self._write_state({"brief_file": "docs/brief.md"})
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        self.assertEqual(result.get("metadata", {}).get("brief_file"), "docs/brief.md")

    def test_spec_file_stored_in_queue_metadata(self):
        """plan_to_queue reads spec_file from state context and stores in metadata."""
        self._write_state({"spec_file": "docs/spec.md"})
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        self.assertEqual(result.get("metadata", {}).get("spec_file"), "docs/spec.md")

    def test_charter_file_stored_in_queue_metadata(self):
        """plan_to_queue reads charter_file from state context and stores in metadata."""
        self._write_state({"charter_file": "docs/charter.md"})
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        self.assertEqual(result.get("metadata", {}).get("charter_file"), "docs/charter.md")

    def test_governance_mode_stored_in_queue_metadata(self):
        """plan_to_queue reads governance_mode from state context and stores in metadata."""
        self._write_state({"governance_mode": "strict"})
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        self.assertEqual(result.get("metadata", {}).get("governance_mode"), "strict")

    def test_multiple_fields_all_stored(self):
        """plan_to_queue stores all four fields when all are present in state."""
        self._write_state({
            "brief_file": "docs/brief.md",
            "spec_file": "docs/spec.md",
            "charter_file": "docs/charter.md",
            "governance_mode": "relaxed",
        })
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        meta = result.get("metadata", {})
        self.assertEqual(meta.get("brief_file"), "docs/brief.md")
        self.assertEqual(meta.get("spec_file"), "docs/spec.md")
        self.assertEqual(meta.get("charter_file"), "docs/charter.md")
        self.assertEqual(meta.get("governance_mode"), "relaxed")

    def test_no_state_file_no_metadata(self):
        """plan_to_queue returns no metadata key if state file does not exist."""
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        # metadata should be absent or empty
        self.assertFalse(result.get("metadata"))

    def test_state_file_missing_context_no_metadata(self):
        """plan_to_queue returns no metadata if state has no context."""
        state = {
            "version": 1, "phase": 2, "stage": "execution",
            "stage_index": 0, "last_updated": "2026-03-26T00:00:00Z",
        }
        with open(self.state_path, "w") as f:
            json.dump(state, f)
        result = plan_to_queue(self.plan_path, "my-feature", state_path=self.state_path)
        self.assertFalse(result.get("metadata"))


# --- Charter-to-queue tests ---

_SAMPLE_CHARTER = """\
---
goal: "Add governance modes"
non_negotiables:
  - "No breaking changes"
success_criteria:
  - "All tests pass"
governance_mode: "light"
---

# Sprint Breakdown

## Sprint 1: Security Hardening [complexity: medium]

Tasks for security hardening.

## Sprint 2: Feature Build [complexity: complex]

Building the feature.
**Dependencies:** Sprint 1

## Sprint 3: Polish [complexity: simple]

Final polish.
**Dependencies:** Sprint 1, Sprint 2
"""


class TestCharterToQueue(unittest.TestCase):
    def test_parses_sprints_from_charter_body(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature")
        self.assertEqual(len(result["sprints"]), 3)

    def test_extracts_titles(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature")
        titles = [s["title"] for s in result["sprints"]]
        self.assertIn("Security Hardening", titles)
        self.assertIn("Feature Build", titles)
        self.assertIn("Polish", titles)

    def test_extracts_complexity_from_bracket_tag(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["complexity"], "medium")
        self.assertEqual(sprints[2]["complexity"], "complex")
        self.assertEqual(sprints[3]["complexity"], "simple")

    def test_extracts_dependencies(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["depends_on"], [])
        self.assertEqual(sprints[2]["depends_on"], [1])
        self.assertEqual(sprints[3]["depends_on"], [1, 2])

    def test_returns_queue_dict_with_expected_keys(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature")
        self.assertIn("feature", result)
        self.assertIn("created", result)
        self.assertIn("sprints", result)
        self.assertEqual(result["feature"], "my-feature")

    def test_branch_naming(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature", base_branch="feat")
        sprints = {s["id"]: s for s in result["sprints"]}
        self.assertEqual(sprints[1]["branch"], "feat/my-feature-sprint-1")

    def test_default_complexity_when_no_bracket_tag(self):
        charter = "---\ngoal: test\n---\n## Sprint 1: Simple Task\nContent here."
        result = charter_to_queue(charter, "feat")
        self.assertEqual(result["sprints"][0]["complexity"], "medium")

    def test_empty_charter_body_raises(self):
        charter = "---\ngoal: test\n---\nNo sprint headings here."
        with self.assertRaises(ValueError):
            charter_to_queue(charter, "feat")

    def test_sprint_fields_complete(self):
        result = charter_to_queue(_SAMPLE_CHARTER, "my-feature")
        sprint = result["sprints"][0]
        for key in ("id", "title", "status", "complexity", "branch",
                    "depends_on", "pr", "retries", "max_retries", "error_log"):
            self.assertIn(key, sprint)
        self.assertEqual(sprint["status"], "pending")
        self.assertIsNone(sprint["pr"])

    def test_circular_dependency_raises(self):
        charter = (
            "---\ngoal: test\n---\n"
            "## Sprint 1: A [complexity: simple]\n**Dependencies:** Sprint 2\n"
            "## Sprint 2: B [complexity: simple]\n**Dependencies:** Sprint 1\n"
        )
        with self.assertRaises(ValueError):
            charter_to_queue(charter, "feat")
