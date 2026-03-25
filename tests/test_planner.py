"""Tests for lib/planner.py — shared sprint heading parser.

Also covers integration: _extract_plan_section in supervisor uses _parse_sprint_headings
for sprint-type fragments.
"""
import unittest

from lib.planner import _parse_sprint_headings
from lib.supervisor import _extract_plan_section


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
