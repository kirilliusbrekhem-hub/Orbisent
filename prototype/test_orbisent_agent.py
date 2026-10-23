"""Basic tests for Orbisent Prototype 0.1 (standard library only).

Run from the repository root:
    python3 -m unittest discover -s prototype -v
"""

import tempfile
import unittest
from pathlib import Path

import orbisent_agent as agent


class VerifyFilesTest(unittest.TestCase):
    def setUp(self):
        # Every test gets a fresh, empty temporary folder that is removed afterwards.
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "demo"
        self.contents = agent.build_file_contents("Launch the demo", "demo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_files_present_passes(self):
        agent.create_project(self.project, self.contents)
        self.assertEqual(agent.verify_files(self.project), [])

    def test_missing_file_is_reported(self):
        agent.create_project(self.project, self.contents)
        (self.project / "TASKS.md").unlink()
        problems = agent.verify_files(self.project)
        self.assertEqual(len(problems), 1)
        self.assertIn("Missing", problems[0])
        self.assertIn("TASKS.md", problems[0])

    def test_empty_file_is_reported(self):
        agent.create_project(self.project, self.contents)
        (self.project / "LAUNCH_PLAN.md").write_text("", encoding="utf-8")
        self.assertIn("Empty", agent.verify_files(self.project)[0])

    def test_wrong_content_is_reported(self):
        agent.create_project(self.project, self.contents)
        (self.project / "TASKS.md").write_text("hello", encoding="utf-8")
        self.assertIn("Unexpected content", agent.verify_files(self.project)[0])

    def test_missing_folder_reports_every_file(self):
        self.assertEqual(len(agent.verify_files(self.project)), len(agent.EXPECTED_FILES))


class SafetyTest(unittest.TestCase):
    def test_existing_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo"
            project.mkdir()
            (project / "README.md").write_text("# My own notes\n", encoding="utf-8")

            completed, skipped, errors = agent.create_project(
                project, agent.build_file_contents("Launch", "demo"))

            self.assertEqual((project / "README.md").read_text(encoding="utf-8"), "# My own notes\n")
            self.assertTrue(any("README.md" in s for s in skipped))
            self.assertEqual(errors, [])
            self.assertEqual(len(completed), 2)  # Only TASKS.md and LAUNCH_PLAN.md were created.

    def test_folder_name_cannot_escape_base_dir(self):
        self.assertEqual(agent.make_folder_name("../../etc"), "etc")
        self.assertEqual(agent.make_folder_name("!!!"), "project")


if __name__ == "__main__":
    unittest.main()
