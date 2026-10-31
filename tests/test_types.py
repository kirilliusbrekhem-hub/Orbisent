"""Tests for orbisent.types (standard library only).

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""

import dataclasses
import unittest

from orbisent.types import GoalSpec, Request


class RequestTest(unittest.TestCase):
    def test_defaults(self):
        request = Request("Prepare my project folder")
        self.assertEqual((request.text, request.explicit_task, dict(request.options)),
                         ("Prepare my project folder", None, {}))

    def test_is_frozen(self):
        request = Request("goal")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            request.text = "other"

    def test_options_are_a_read_only_copy(self):
        options = {"name": "bakery"}
        request = Request("goal", options=options)
        options["name"] = "changed"
        self.assertEqual(request.options["name"], "bakery")
        with self.assertRaises(TypeError):
            request.options["name"] = "changed"

    def test_rejects_wrong_types(self):
        for kwargs in ({"text": None}, {"text": b"bytes"}, {"text": "g", "explicit_task": 3},
                       {"text": "g", "options": ["not", "a", "mapping"]},
                       {"text": "g", "options": {1: "non-string key"}},
                       {"text": "g", "options": {"nested": ["list"]}},
                       {"text": "g", "options": {"float": 1.5}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                Request(**kwargs)

    def test_scalar_option_values_are_allowed(self):
        request = Request("g", options={"s": "x", "i": 1, "b": True, "n": None})
        self.assertEqual(dict(request.options), {"s": "x", "i": 1, "b": True, "n": None})

    def test_equality(self):
        self.assertEqual(Request("g", "prepare_project", {"a": 1}), Request("g", "prepare_project", {"a": 1}))
        self.assertNotEqual(Request("g"), Request("h"))


class GoalSpecTest(unittest.TestCase):
    def test_decided(self):
        spec = GoalSpec.decided("Prepare my project folder", "prepare_project", "rules")
        self.assertFalse(spec.needs_clarification)
        self.assertEqual((spec.task_type, spec.source, spec.confidence), ("prepare_project", "rules", 1.0))
        self.assertEqual((spec.ambiguities, spec.candidates, dict(spec.parameters)), ((), (), {}))

    def test_unclear(self):
        spec = GoalSpec.unclear("goal", "rules", ["reason one"], candidates=["a", "b"])
        self.assertTrue(spec.needs_clarification)
        self.assertEqual((spec.task_type, spec.confidence), (None, 0.0))
        self.assertEqual(spec.ambiguities, ("reason one",))
        self.assertEqual(spec.candidates, ("a", "b"))

    def test_sequences_become_tuples_and_mappings_become_read_only(self):
        reasons = ["why"]
        spec = GoalSpec.unclear("goal", "rules", reasons)
        reasons.append("later change")
        self.assertEqual(spec.ambiguities, ("why",))
        decided = GoalSpec.decided("goal", "t", "explicit", parameters={"project_name": "bakery"})
        with self.assertRaises(TypeError):
            decided.parameters["project_name"] = "other"

    def test_is_frozen(self):
        spec = GoalSpec.decided("goal", "t", "rules")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.task_type = "other"

    def test_unclear_must_explain_why(self):
        with self.assertRaises(ValueError):
            GoalSpec.unclear("goal", "rules", [])

    def test_inconsistent_shapes_are_rejected(self):
        with self.assertRaises(ValueError):  # Unclear but confident.
            GoalSpec(text="g", task_type=None, source="rules", confidence=0.5, ambiguities=("x",))
        with self.assertRaises(ValueError):  # Decided but with zero confidence.
            GoalSpec(text="g", task_type="t", source="rules", confidence=0.0)
        with self.assertRaises(ValueError):  # Decided but still ambiguous.
            GoalSpec(text="g", task_type="t", source="rules", confidence=1.0, ambiguities=("x",))
        with self.assertRaises(ValueError):  # Decided but with candidates.
            GoalSpec(text="g", task_type="t", source="rules", confidence=1.0, candidates=("a", "b"))

    def test_rejects_wrong_types_and_ranges(self):
        with self.assertRaises(ValueError):
            GoalSpec.decided("g", "t", "rules", confidence=1.5)
        for kwargs in ({"text": None, "task_type": "t", "source": "rules", "confidence": 1.0},
                       {"text": "g", "task_type": "", "source": "rules", "confidence": 1.0},
                       {"text": "g", "task_type": "t", "source": "", "confidence": 1.0},
                       {"text": "g", "task_type": "t", "source": "rules", "confidence": True},
                       {"text": "g", "task_type": "t", "source": "rules", "confidence": "1"},
                       {"text": "g", "task_type": None, "source": "rules", "ambiguities": "a string"},
                       {"text": "g", "task_type": None, "source": "rules", "ambiguities": (1,)},
                       {"text": "g", "task_type": "t", "source": "rules", "confidence": 1.0,
                        "parameters": {"k": object()}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                GoalSpec(**kwargs)


if __name__ == "__main__":
    unittest.main()
