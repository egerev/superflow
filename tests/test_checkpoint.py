"""Tests for checkpoint save/load system — TDD approach."""
import json
import os
import shutil
import tempfile
import unittest

from lib.checkpoint import save_checkpoint, load_checkpoint, load_all_checkpoints


class TestCheckpointSaveLoad(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_save_and_load_roundtrip(self):
        data = {"sprint_id": 1, "phase": "implementation", "progress": 50}
        save_checkpoint(self.cp_dir, 1, data)
        loaded = load_checkpoint(self.cp_dir, 1)
        self.assertEqual(loaded, data)

    def test_load_missing_returns_none(self):
        result = load_checkpoint(self.cp_dir, 99)
        self.assertIsNone(result)

    def test_directory_auto_creation(self):
        nested = os.path.join(self.tmpdir, "deep", "nested", "checkpoints")
        data = {"sprint_id": 5, "status": "ok"}
        save_checkpoint(nested, 5, data)
        self.assertTrue(os.path.isdir(nested))
        loaded = load_checkpoint(nested, 5)
        self.assertEqual(loaded, data)

    def test_overwrite_existing_checkpoint(self):
        save_checkpoint(self.cp_dir, 1, {"v": 1})
        save_checkpoint(self.cp_dir, 1, {"v": 2})
        loaded = load_checkpoint(self.cp_dir, 1)
        self.assertEqual(loaded["v"], 2)

    def test_file_naming(self):
        save_checkpoint(self.cp_dir, 3, {"x": 1})
        expected_path = os.path.join(self.cp_dir, "sprint-3.json")
        self.assertTrue(os.path.exists(expected_path))

    def test_file_is_valid_json(self):
        save_checkpoint(self.cp_dir, 1, {"key": "value"})
        path = os.path.join(self.cp_dir, "sprint-1.json")
        with open(path) as f:
            parsed = json.load(f)
        self.assertEqual(parsed["key"], "value")


class TestLoadAllCheckpoints(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_load_all_empty_dir(self):
        result = load_all_checkpoints(self.cp_dir)
        self.assertEqual(result, [])

    def test_load_all_multiple(self):
        save_checkpoint(self.cp_dir, 1, {"id": 1})
        save_checkpoint(self.cp_dir, 2, {"id": 2})
        save_checkpoint(self.cp_dir, 3, {"id": 3})
        result = load_all_checkpoints(self.cp_dir)
        self.assertEqual(len(result), 3)
        ids = sorted(r["id"] for r in result)
        self.assertEqual(ids, [1, 2, 3])

    def test_load_all_ignores_non_checkpoint_files(self):
        save_checkpoint(self.cp_dir, 1, {"id": 1})
        # Write a non-checkpoint file
        with open(os.path.join(self.cp_dir, "readme.txt"), "w") as f:
            f.write("not a checkpoint")
        result = load_all_checkpoints(self.cp_dir)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
