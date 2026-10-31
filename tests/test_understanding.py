"""Tests for orbisent.understanding, including exact parity with Prototype 0.3.

Run from the repository root:
    python3 -m unittest discover -s tests -v

The parity tests import prototype/orbisent_agent.py read-only, as the reference
implementation. They never call anything that touches the file system.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

from orbisent.types import GoalSpec, Request
from orbisent.understanding import (
    DEFAULT_KEYWORDS,
    ChainedInterpreter,
    ExplicitInterpreter,
    RuleInterpreter,
    clean_goal,
    default_interpreter,
)

PROTOTYPE_DIR = Path(__file__).resolve().parent.parent / "prototype"
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.append(str(PROTOTYPE_DIR))  # Appended, so prototype modules can't shadow anything else.
import orbisent_agent as prototype  # noqa: E402  (Prototype 0.3, the reference)

# Goals used to compare 1.0 with 0.3. They include every goal used in the prototype's own tests and
# documentation, plus edge cases: case, punctuation, whitespace, plurals, partial words and Unicode.
PARITY_GOALS = [
    "Prepare my project folder for launch",
    "Create a launch checklist for my app",
    "Launch my bakery website",
    "Make me a sandwich",
    "Prepare my project folder and a launch checklist",
    "Prepare my project folder and a checklist",
    "Set up a project for my band",
    "I need a CHECKLIST!",
    "Write about checklisting",
    "Prepare my project folder",
    "Create a launch checklist",
    "Launch my bakery",
    "Goal",
    "x",
    "checklists for everyone",
    "a check list",
    "a check-list",
    "a check\nlist",
    "  prepare   the\tproject  ",
    "PREPARE PROJECT",
    "prepare-project",
    "prepare_project",
    "setup project",
    "set up my project",
    "setupproject",
    "newproject",
    "new project",
    "a new projects",
    "scaffold",
    "scaffolding",
    "project directory",
    "project-directory/",
    "my project folder's checklist",
    "Prépare my project folder",
    "чек-лист checklist",
    "проект",
    "checklist" * 3,
    "🚀 checklist 🚀",
    "…",
    "",
    "   ",
]


def prototype_result(goal):
    """What Prototype 0.3 decides for a goal: (task_type or None, matches), or 'empty' if it refuses it."""
    cleaned = prototype.clean_goal(goal)
    if not cleaned:
        return "empty"
    matches = prototype.classify_goal(cleaned)
    return (matches[0] if len(matches) == 1 else None, matches)


class PrototypeParityTest(unittest.TestCase):
    def test_keyword_table_matches_the_prototype(self):
        expected = {task_id: task.keywords for task_id, task in prototype.TASK_TYPES.items()}
        self.assertEqual(DEFAULT_KEYWORDS, expected)
        self.assertEqual(list(DEFAULT_KEYWORDS), list(prototype.TASK_TYPES))  # Same order.

    def test_clean_goal_matches_the_prototype(self):
        for goal in PARITY_GOALS:
            with self.subTest(goal=goal):
                self.assertEqual(clean_goal(goal), prototype.clean_goal(goal))

    def test_rule_matches_equal_classify_goal(self):
        rules = RuleInterpreter()
        for goal in PARITY_GOALS:
            with self.subTest(goal=goal):
                self.assertEqual(rules.matches(clean_goal(goal)), prototype.classify_goal(clean_goal(goal)))

    def test_default_chain_decides_exactly_like_the_prototype(self):
        interpreter = default_interpreter()
        for goal in PARITY_GOALS:
            with self.subTest(goal=goal):
                spec = interpreter.interpret(Request(goal))
                expected = prototype_result(goal)
                if expected == "empty":
                    self.assertTrue(spec.needs_clarification)
                    self.assertEqual(spec.ambiguities, ("the goal must not be empty",))
                    continue
                task_type, matches = expected
                self.assertEqual(spec.task_type, task_type)
                self.assertEqual(spec.text, prototype.clean_goal(goal))
                if task_type is None:
                    self.assertEqual(list(spec.candidates), matches if len(matches) > 1 else [])

    def test_explicit_task_wins_like_the_prototype(self):
        # 0.3: "--task create_launch_checklist" on a prepare_project goal creates the checklist.
        spec = default_interpreter().interpret(Request("Prepare my project folder", "create_launch_checklist"))
        self.assertEqual((spec.task_type, spec.source), ("create_launch_checklist", "explicit"))
        spec = default_interpreter().interpret(Request("Launch my bakery", "prepare_project"))
        self.assertEqual((spec.task_type, spec.source), ("prepare_project", "explicit"))

    def test_explanations_match_the_prototype_wording(self):
        interpreter = default_interpreter()
        unknown = interpreter.interpret(Request("Make me a sandwich"))
        self.assertEqual(unknown.ambiguities, ("it does not match any task type Orbisent knows",))
        ambiguous = interpreter.interpret(Request("Prepare my project folder and a checklist"))
        self.assertEqual(ambiguous.ambiguities,
                         ("it matches more than one task type (prepare_project, create_launch_checklist)",))
        self.assertEqual(ambiguous.candidates, ("prepare_project", "create_launch_checklist"))


class ExplicitInterpreterTest(unittest.TestCase):
    def test_passes_when_no_task_given(self):
        self.assertIsNone(ExplicitInterpreter().interpret(Request("Prepare my project folder")))

    def test_known_task(self):
        spec = ExplicitInterpreter().interpret(Request("  my \n goal ", "prepare_project"))
        self.assertEqual((spec.text, spec.task_type, spec.source, spec.confidence),
                         ("my goal", "prepare_project", "explicit", 1.0))

    def test_unknown_task_is_refused(self):
        spec = ExplicitInterpreter().interpret(Request("Prepare my project folder", "delete_everything"))
        self.assertTrue(spec.needs_clarification)
        self.assertEqual(spec.ambiguities,
                         ("unknown task type 'delete_everything' (known: prepare_project, create_launch_checklist)",))

    def test_task_names_are_exact(self):
        for name in ("Prepare_Project", " prepare_project", "prepare project", ""):
            with self.subTest(name=name):
                self.assertTrue(ExplicitInterpreter().interpret(Request("g", name)).needs_clarification)

    def test_custom_task_types(self):
        interpreter = ExplicitInterpreter(["only_this"])
        self.assertEqual(interpreter.interpret(Request("g", "only_this")).task_type, "only_this")
        self.assertTrue(interpreter.interpret(Request("g", "prepare_project")).needs_clarification)


class RuleInterpreterTest(unittest.TestCase):
    def test_clear_goals(self):
        rules = RuleInterpreter()
        self.assertEqual(rules.interpret(Request("Set up a project for my band")).task_type, "prepare_project")
        spec = rules.interpret(Request("I need a CHECKLIST!"))
        self.assertEqual((spec.task_type, spec.source, spec.confidence), ("create_launch_checklist", "rules", 1.0))

    def test_ignores_explicit_task(self):
        # The rule interpreter only reads the text; choosing between explicit and rules is the chain's job.
        spec = RuleInterpreter().interpret(Request("Create a launch checklist", "prepare_project"))
        self.assertEqual(spec.task_type, "create_launch_checklist")

    def test_never_guesses(self):
        for goal in ("Make me a sandwich", "Prepare my project folder and a checklist", "checklisting"):
            with self.subTest(goal=goal):
                spec = RuleInterpreter().interpret(Request(goal))
                self.assertIsNone(spec.task_type)
                self.assertEqual(spec.confidence, 0.0)
                self.assertTrue(spec.ambiguities)

    def test_custom_keywords(self):
        rules = RuleInterpreter({"greet": ("say hello",)})
        self.assertEqual(rules.interpret(Request("Please SAY hello!")).task_type, "greet")
        self.assertTrue(rules.interpret(Request("hello")).needs_clarification)

    def test_keywords_that_can_never_match_are_rejected(self):
        for bad in ("Checklist", "check  list", " checklist", "check-list", "", "chéck"):
            with self.subTest(keyword=bad), self.assertRaises(ValueError):
                RuleInterpreter({"t": (bad,)})
        with self.assertRaises(TypeError):
            RuleInterpreter({"t": "checklist"})  # A string, not a sequence of strings.
        with self.assertRaises(ValueError):
            RuleInterpreter({"t": (None,)})

    def test_keyword_table_is_copied(self):
        table = {"t": ["word"]}
        rules = RuleInterpreter(table)
        table["t"].append("other")
        self.assertEqual(rules.keywords, {"t": ("word",)})


class Spy:
    """A fake interpreter that records calls and returns a fixed answer."""

    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def interpret(self, request):
        self.calls += 1
        return self.answer


class ChainedInterpreterTest(unittest.TestCase):
    def test_first_answer_wins_and_later_interpreters_are_not_asked(self):
        first = Spy(GoalSpec.decided("g", "a", "first"))
        second = Spy(GoalSpec.decided("g", "b", "second"))
        self.assertEqual(ChainedInterpreter([first, second]).interpret(Request("g")).task_type, "a")
        self.assertEqual((first.calls, second.calls), (1, 0))

    def test_none_passes_to_the_next(self):
        passing, deciding = Spy(None), Spy(GoalSpec.decided("g", "b", "second"))
        self.assertEqual(ChainedInterpreter([passing, deciding]).interpret(Request("g")).task_type, "b")
        self.assertEqual(passing.calls, 1)

    def test_unclear_answer_stops_the_chain(self):
        unclear, later = Spy(GoalSpec.unclear("g", "first", ["no"])), Spy(GoalSpec.decided("g", "b", "s"))
        spec = ChainedInterpreter([unclear, later]).interpret(Request("g"))
        self.assertTrue(spec.needs_clarification)
        self.assertEqual(later.calls, 0)

    def test_invalid_explicit_task_never_falls_through_to_rules(self):
        rules = Spy(GoalSpec.decided("g", "prepare_project", "rules"))
        spec = ChainedInterpreter([ExplicitInterpreter(), rules]).interpret(
            Request("Prepare my project folder", "nope"))
        self.assertTrue(spec.needs_clarification)
        self.assertEqual(rules.calls, 0)

    def test_everyone_passing_gives_unclear_not_a_guess(self):
        spec = ChainedInterpreter([Spy(None), Spy(None)]).interpret(Request("g"))
        self.assertEqual((spec.task_type, spec.source, spec.ambiguities),
                         (None, "chain", ("no interpreter could classify the goal",)))
        self.assertTrue(ChainedInterpreter([]).interpret(Request("g")).needs_clarification)

    def test_empty_goal_is_refused_before_any_interpreter_runs(self):
        spy = Spy(GoalSpec.decided("g", "a", "s"))
        for text in ("", "   ", "\n\t"):
            with self.subTest(text=text):
                spec = ChainedInterpreter([spy]).interpret(Request(text, "prepare_project"))
                self.assertEqual(spec.ambiguities, ("the goal must not be empty",))
        self.assertEqual(spy.calls, 0)

    def test_wrong_return_type_is_an_error(self):
        with self.assertRaises(TypeError):
            ChainedInterpreter([Spy("prepare_project")]).interpret(Request("g"))


class DeterminismAndIsolationTest(unittest.TestCase):
    def test_same_request_gives_equal_results(self):
        interpreter = default_interpreter()
        for goal in PARITY_GOALS:
            with self.subTest(goal=goal):
                self.assertEqual(interpreter.interpret(Request(goal)), interpreter.interpret(Request(goal)))

    def test_no_file_or_network_access(self):
        # Goal understanding is pure computation: opening files or sockets would be a bug.
        blocked = mock.Mock(side_effect=AssertionError("unexpected I/O"))
        with mock.patch("builtins.open", blocked), mock.patch("socket.socket", blocked), \
                mock.patch("os.open", blocked):
            interpreter = default_interpreter()
            for goal in PARITY_GOALS:
                interpreter.interpret(Request(goal))
                interpreter.interpret(Request(goal, "prepare_project"))
        blocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
