"""Tests for the Orbisent prototype (0.2 behaviour plus 0.3 step execution; standard library only).

Run from the repository root:
    python3 -m unittest discover -s prototype -v
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import orbisent_agent as agent
from engine import COMPLETED, FAILED, SKIPPED

PREPARE = agent.TASK_TYPES["prepare_project"]
CHECKLIST = agent.TASK_TYPES["create_launch_checklist"]


def run_cli(args, answers=("y",)):
    """Run main() with the given arguments and typed answers; return (exit code, printed text)."""
    replies = iter(answers)

    def fake_input(prompt):
        print(prompt, end="")  # Like the real input(), show the question.
        try:
            return next(replies)
        except StopIteration:
            raise EOFError

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = agent.main(args, input_func=fake_input)
    return code, output.getvalue()


class TempDirTest(unittest.TestCase):
    """Gives every test a fresh, empty temporary folder that is removed afterwards."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def all_files(self):
        return sorted(p.relative_to(self.base).as_posix() for p in self.base.rglob("*"))


class VerifyFilesTest(TempDirTest):
    """File verification for prepare_project (the Prototype 0.1 behaviour)."""

    def setUp(self):
        super().setUp()
        self.project = self.base / "demo"
        self.contents = agent.build_contents(PREPARE, "Launch the demo", "demo")

    def test_all_files_present_passes(self):
        agent.create_project(self.project, self.contents)
        self.assertEqual(agent.verify_files(self.project, PREPARE), [])

    def test_missing_file_is_reported(self):
        agent.create_project(self.project, self.contents)
        (self.project / "TASKS.md").unlink()
        problems = agent.verify_files(self.project, PREPARE)
        self.assertEqual(len(problems), 1)
        self.assertIn("Missing", problems[0])
        self.assertIn("TASKS.md", problems[0])

    def test_empty_file_is_reported(self):
        agent.create_project(self.project, self.contents)
        (self.project / "LAUNCH_PLAN.md").write_text("", encoding="utf-8")
        self.assertIn("Empty", agent.verify_files(self.project, PREPARE)[0])

    def test_wrong_content_is_reported(self):
        agent.create_project(self.project, self.contents)
        (self.project / "TASKS.md").write_text("hello", encoding="utf-8")
        self.assertIn("Unexpected content", agent.verify_files(self.project, PREPARE)[0])

    def test_missing_folder_reports_every_file(self):
        self.assertEqual(len(agent.verify_files(self.project, PREPARE)), len(PREPARE.files))

    def test_directory_in_place_of_file_is_reported(self):
        (self.project / "README.md").mkdir(parents=True)
        agent.create_project(self.project, self.contents)
        self.assertEqual(agent.verify_files(self.project, PREPARE),
                         [f"Not a file: {self.project / 'README.md'}"])


class ContentValidationTest(unittest.TestCase):
    """Every task type's generated text passes its checks, and broken text fails them."""

    def test_generated_files_pass_their_checks(self):
        for task in agent.TASK_TYPES.values():
            for spec in task.files:
                with self.subTest(task=task.identifier, file=spec.name):
                    self.assertEqual(agent.check_text(spec.build("My goal", "demo"), spec), [])

    def test_readme_needs_goal_and_file_list(self):
        spec = PREPARE.files[0]
        problems = agent.check_text("# demo\n\nJust a title.\n", spec)
        self.assertTrue(any("**Goal:**" in p for p in problems))
        self.assertTrue(any("## Files" in p for p in problems))

    def test_tasks_need_enough_checkboxes(self):
        spec = PREPARE.files[1]
        problems = agent.check_text("# Tasks\n\nGoal: x\n\n- [ ] one\n- [ ] two\n", spec)
        self.assertEqual(problems, ["Too few checkbox items (found 2, expected at least 5)"])

    def test_launch_plan_needs_numbered_steps(self):
        spec = PREPARE.files[2]
        problems = agent.check_text("# Launch Plan\n\nGoal: x\n\n- step\n", spec)
        self.assertEqual(problems, ["Too few numbered steps (found 0, expected at least 5)"])

    def test_checklist_needs_sections_and_checkboxes(self):
        spec = CHECKLIST.files[0]
        text = "# Launch Checklist\n\nGoal: x\n\n## Only section\n\n- [ ] one item\n"
        problems = agent.check_text(text, spec)
        self.assertIn("Too few checkbox items (found 1, expected at least 12)", problems)
        self.assertIn("Too few '## ' sections (found 1, expected at least 4)", problems)

    def test_checklist_needs_title(self):
        spec = CHECKLIST.files[0]
        text = CHECKLIST.files[0].build("x", "demo").replace("# Launch Checklist", "# Notes")
        self.assertEqual(len(agent.check_text(text, spec)), 1)

    def test_ticked_boxes_still_count(self):
        spec = CHECKLIST.files[0]
        text = spec.build("x", "demo").replace("- [ ]", "- [x]")
        self.assertEqual(agent.check_text(text, spec), [])


class ClassifyGoalTest(unittest.TestCase):
    def test_clear_goals(self):
        self.assertEqual(agent.classify_goal("Prepare my project folder for launch"), ["prepare_project"])
        self.assertEqual(agent.classify_goal("Set up a project for my band"), ["prepare_project"])
        self.assertEqual(agent.classify_goal("Create a launch checklist for my app"),
                         ["create_launch_checklist"])
        self.assertEqual(agent.classify_goal("I need a CHECKLIST!"), ["create_launch_checklist"])

    def test_unknown_goal(self):
        self.assertEqual(agent.classify_goal("Make me a sandwich"), [])

    def test_ambiguous_goal(self):
        self.assertEqual(agent.classify_goal("Prepare my project folder and a launch checklist"),
                         ["prepare_project", "create_launch_checklist"])

    def test_keywords_match_whole_words_only(self):
        self.assertEqual(agent.classify_goal("Write about checklisting"), [])


class CommandLineTest(TempDirTest):
    def test_prepare_project_end_to_end(self):
        code, out = run_cli(["Prepare my project folder for launch", "--base-dir", str(self.base)])
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertIn("Task type: prepare_project (chosen from keywords in the goal)", out)
        self.assertIn("SUCCESS", out)
        folder = "prepare-my-project-folder-for-launch"
        self.assertEqual(self.all_files(), [folder, f"{folder}/LAUNCH_PLAN.md",
                                            f"{folder}/README.md", f"{folder}/TASKS.md"])

    def test_launch_checklist_end_to_end(self):
        code, out = run_cli(["Create a launch checklist", "--name", "app", "--base-dir", str(self.base)])
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertIn("Task type: create_launch_checklist", out)
        self.assertEqual(self.all_files(), ["app", "app/LAUNCH_CHECKLIST.md"])
        text = (self.base / "app" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("Goal: Create a launch checklist", text)

    def test_explicit_task_wins_over_keywords(self):
        code, out = run_cli(["Prepare my project folder", "--task", "create_launch_checklist",
                             "--name", "p", "--base-dir", str(self.base)])
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertIn("chosen with --task", out)
        self.assertEqual(self.all_files(), ["p", "p/LAUNCH_CHECKLIST.md"])

    def test_explicit_task_for_unknown_goal(self):
        code, _ = run_cli(["Launch my bakery", "--task", "prepare_project", "--base-dir", str(self.base)])
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertEqual(len(self.all_files()), 4)

    def test_unknown_goal_creates_nothing(self):
        code, out = run_cli(["Make me a sandwich", "--base-dir", str(self.base)])
        self.assertEqual(code, agent.EXIT_UNCLASSIFIED)
        self.assertIn("does not match any task type", out)
        self.assertIn("Nothing was created", out)
        self.assertEqual(self.all_files(), [])

    def test_ambiguous_goal_creates_nothing(self):
        code, out = run_cli(["Prepare my project folder and a checklist", "--base-dir", str(self.base)])
        self.assertEqual(code, agent.EXIT_UNCLASSIFIED)
        self.assertIn("matches more than one task type", out)
        self.assertEqual(self.all_files(), [])

    def test_unclassified_goal_never_asks_for_permission(self):
        with mock.patch.object(agent, "create_project") as create:
            code, out = run_cli(["Make me a sandwich", "--base-dir", str(self.base)], answers=())
        self.assertEqual(code, agent.EXIT_UNCLASSIFIED)
        self.assertNotIn("Proceed with this plan?", out)
        create.assert_not_called()

    def test_cancel_creates_nothing(self):
        for answers in (("n",), ("",), ()):  # "n", just Enter, and no input at all.
            with self.subTest(answers=answers):
                code, out = run_cli(["Create a launch checklist", "--base-dir", str(self.base)], answers)
                self.assertEqual(code, agent.EXIT_INCOMPLETE)
                self.assertIn("Cancelled. Nothing was changed.", out)
                self.assertEqual(self.all_files(), [])

    def test_plan_is_shown_before_asking(self):
        _, out = run_cli(["Create a launch checklist", "--base-dir", str(self.base)], answers=("n",))
        self.assertLess(out.index("Plan:"), out.index("Proceed with this plan?"))
        self.assertIn("Write LAUNCH_CHECKLIST.md", out)

    def test_invalid_task_type_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as exit_info:
            agent.main(["Anything", "--task", "delete_everything", "--base-dir", str(self.base)])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("invalid choice", err.getvalue())
        self.assertEqual(self.all_files(), [])

    def test_empty_goal_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            agent.main(["   ", "--base-dir", str(self.base)])
        self.assertEqual(self.all_files(), [])

    def test_repeated_request_is_safe(self):
        args = ["Create a launch checklist", "--name", "app", "--base-dir", str(self.base), "--yes"]
        run_cli(args)
        path = self.base / "app" / "LAUNCH_CHECKLIST.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nMy own note\n", encoding="utf-8")
        code, out = run_cli(args)
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertIn("File already exists, left unchanged", out)
        self.assertIn("My own note", path.read_text(encoding="utf-8"))

    def test_base_dir_that_is_a_file_is_reported(self):
        not_a_folder = self.base / "afile"
        not_a_folder.write_text("keep me", encoding="utf-8")
        code, out = run_cli(["Create a launch checklist", "--base-dir", str(not_a_folder), "--yes"])
        self.assertEqual(code, agent.EXIT_INCOMPLETE)
        self.assertIn("Could not create folder", out)
        self.assertIn("INCOMPLETE", out)
        self.assertEqual(not_a_folder.read_text(encoding="utf-8"), "keep me")


class SafetyTest(TempDirTest):
    def test_existing_file_is_never_overwritten(self):
        project = self.base / "demo"
        project.mkdir()
        (project / "README.md").write_text("# My own notes\n", encoding="utf-8")

        completed, skipped, errors = agent.create_project(
            project, agent.build_contents(PREPARE, "Launch", "demo"))

        self.assertEqual((project / "README.md").read_text(encoding="utf-8"), "# My own notes\n")
        self.assertTrue(any("README.md" in s for s in skipped))
        self.assertEqual(errors, [])
        self.assertEqual(len(completed), 2)  # Only TASKS.md and LAUNCH_PLAN.md were created.

    def test_folder_name_cannot_escape_base_dir(self):
        self.assertEqual(agent.make_folder_name("../../etc"), "etc")
        self.assertEqual(agent.make_folder_name("!!!"), "project")

    def test_path_traversal_stays_inside_base_dir(self):
        inner = self.base / "inner"  # Projects go here; nothing may appear next to it.
        for name in ("../../escape", "/etc/passwd", "..", "a/../../b"):
            with self.subTest(name=name):
                run_cli(["Create a launch checklist", "--name", name, "--base-dir", str(inner), "--yes"])
        self.assertEqual([p.name for p in self.base.iterdir()], ["inner"])
        self.assertEqual(sorted(p.name for p in inner.iterdir()),
                         ["a-b", "escape", "etc-passwd", "project"])

    def test_file_creation_failure_is_reported(self):
        project = self.base / "demo"
        with mock.patch("builtins.open", side_effect=PermissionError("Permission denied")):
            completed, skipped, errors = agent.create_project(
                project, agent.build_contents(CHECKLIST, "Launch", "demo"))
        self.assertEqual(completed, [f"Created folder: {project}"])
        self.assertEqual(len(errors), 1)
        self.assertIn("Permission denied", errors[0])
        self.assertEqual(agent.verify_files(project, CHECKLIST),
                         [f"Missing: {project / 'LAUNCH_CHECKLIST.md'}"])

    def test_folder_creation_failure_stops_before_files(self):
        project = self.base / "demo"
        with mock.patch.object(Path, "mkdir", side_effect=PermissionError("Permission denied")):
            completed, skipped, errors = agent.create_project(
                project, agent.build_contents(PREPARE, "Launch", "demo"))
        self.assertEqual(completed, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Could not create folder", errors[0])


class StepExecutionTest(TempDirTest):
    """Prototype 0.3: the CLI runs the task as ordered, verified steps."""

    def run_prepare(self, *extra, answers=("y",)):
        return run_cli(["Prepare my project folder", "--name", "demo", "--base-dir", str(self.base), *extra],
                       answers)

    def test_every_task_has_one_plan_sentence_per_file(self):
        for task in agent.TASK_TYPES.values():
            with self.subTest(task=task.identifier):
                self.assertEqual(len(task.plan), len(task.files))
                steps = agent.build_steps(task, "Goal", self.base / "p", "p")
                self.assertEqual(len(steps), 1 + len(task.files))

    def test_mismatched_plan_is_rejected(self):
        broken = agent.TaskType("broken", "Broken", ("x",), ("one", "two"), PREPARE.files[:1])
        with self.assertRaises(ValueError):
            agent.build_steps(broken, "Goal", self.base / "p", "p")

    def test_building_the_plan_touches_nothing(self):
        agent.build_steps(PREPARE, "Goal", self.base / "p", "p")
        self.assertEqual(self.all_files(), [])

    def test_plan_shows_every_step_with_its_expected_outcome(self):
        code, out = self.run_prepare(answers=("n",))
        self.assertEqual(code, agent.EXIT_INCOMPLETE)
        plan = out[out.index("Plan:"):out.index("Proceed with this plan?")]
        self.assertEqual(plan.count("Expected:"), 4)
        self.assertIn("not by an AI", plan)
        self.assertIn("at least 5 checkbox items", plan)
        self.assertIn("at least 5 numbered steps", plan)
        self.assertEqual(self.all_files(), [])

    def test_successful_chain_reports_every_step_completed(self):
        code, out = self.run_prepare()
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertEqual(out.count("[completed]"), 4)
        self.assertIn("Steps: 4 completed", out)
        self.assertIn("SUCCESS", out)

    def test_repeated_run_is_all_skipped_and_verified(self):
        self.run_prepare()
        code, out = self.run_prepare()
        self.assertEqual(code, agent.EXIT_SUCCESS)
        self.assertIn("Steps: 4 skipped", out)
        self.assertIn("SUCCESS", out)

    def test_existing_bad_file_fails_verification_and_stops(self):
        project = self.base / "demo"
        project.mkdir()
        (project / "TASKS.md").write_text("hello", encoding="utf-8")

        code, out = self.run_prepare()

        self.assertEqual(code, agent.EXIT_INCOMPLETE)
        self.assertNotIn("SUCCESS", out)
        self.assertIn("[failed] Write TASKS.md", out)
        self.assertIn("Problem: Unexpected content", out)
        self.assertIn("Not run: step 3 failed.", out)
        self.assertIn("INCOMPLETE: step 3 failed", out)
        self.assertEqual((project / "TASKS.md").read_text(encoding="utf-8"), "hello")  # Not overwritten.
        self.assertTrue((project / "README.md").is_file())  # Step 2 ran before the failure.
        self.assertFalse((project / "LAUNCH_PLAN.md").exists())  # Step 4 never ran.

    def test_execution_failure_stops_later_steps(self):
        real_open = open

        def failing_open(path, *args, **kwargs):
            if Path(path).name == "TASKS.md":
                raise PermissionError("Permission denied")
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=failing_open):
            code, out = self.run_prepare()

        self.assertEqual(code, agent.EXIT_INCOMPLETE)
        self.assertIn("Problem: Could not create", out)
        self.assertIn("Permission denied", out)
        self.assertIn("Steps: 2 completed, 1 skipped, 1 failed", out)
        self.assertEqual(self.all_files(), ["demo", "demo/README.md"])

    def test_step_statuses_after_a_run(self):
        project = self.base / "demo"
        steps = agent.build_steps(PREPARE, "Goal", project, "demo")
        project.mkdir()
        (project / "README.md").write_text("# Mine\n", encoding="utf-8")  # Exists but fails the README checks.
        self.assertFalse(agent.run_steps(steps))
        self.assertEqual([s.status for s in steps], [SKIPPED, FAILED, SKIPPED, SKIPPED])
        self.assertEqual((project / "README.md").read_text(encoding="utf-8"), "# Mine\n")

    def test_cancel_with_existing_files_changes_nothing(self):
        project = self.base / "demo"
        project.mkdir()
        (project / "notes.txt").write_text("keep", encoding="utf-8")
        code, out = self.run_prepare(answers=("n",))
        self.assertEqual(code, agent.EXIT_INCOMPLETE)
        self.assertNotIn("=== Orbisent report ===", out)
        self.assertEqual(self.all_files(), ["demo", "demo/notes.txt"])
        self.assertEqual((project / "notes.txt").read_text(encoding="utf-8"), "keep")

    def test_completed_steps_are_verified_by_content(self):
        steps = agent.build_steps(CHECKLIST, "Goal", self.base / "c", "c")
        self.assertTrue(agent.run_steps(steps))
        self.assertEqual([s.status for s in steps], [COMPLETED, COMPLETED])
        self.assertIn("at least 12 checkbox items", steps[1].expected)


if __name__ == "__main__":
    unittest.main()
