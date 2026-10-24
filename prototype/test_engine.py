"""Unit tests for the Orbisent step engine (standard library only).

Run from the repository root:
    python3 -m unittest discover -s prototype -v
"""

import unittest

from engine import COMPLETED, FAILED, PENDING, SKIPPED, SkipStep, Step, StepError, run_steps


def make_step(name, log, result="done", problems=(), raises=None, verify_raises=None):
    """A fake step that records in `log` when its action and verification run."""

    def action():
        log.append(f"{name}:action")
        if raises:
            raise raises
        return result

    def verify():
        log.append(f"{name}:verify")
        if verify_raises:
            raise verify_raises
        return list(problems)

    return Step(f"Step {name}", f"{name} is done", action, verify)


class SuccessfulChainTest(unittest.TestCase):
    def test_steps_start_pending(self):
        step = make_step("a", [])
        self.assertEqual((step.status, step.message, step.problems), (PENDING, "", []))

    def test_all_steps_run_in_order_and_are_verified(self):
        log = []
        steps = [make_step(name, log, result=f"{name} ok") for name in "abc"]
        self.assertTrue(run_steps(steps))
        self.assertEqual(log, ["a:action", "a:verify", "b:action", "b:verify", "c:action", "c:verify"])
        self.assertEqual([s.status for s in steps], [COMPLETED] * 3)
        self.assertEqual([s.message for s in steps], ["a ok", "b ok", "c ok"])

    def test_empty_plan_succeeds(self):
        self.assertTrue(run_steps([]))

    def test_skipped_step_is_still_verified_and_chain_continues(self):
        log = []
        steps = [make_step("a", log, raises=SkipStep("already there")), make_step("b", log)]
        self.assertTrue(run_steps(steps))
        self.assertEqual(log, ["a:action", "a:verify", "b:action", "b:verify"])
        self.assertEqual((steps[0].status, steps[0].message), (SKIPPED, "already there"))
        self.assertEqual(steps[1].status, COMPLETED)


class VerificationFailureTest(unittest.TestCase):
    def test_failed_verification_fails_the_step_and_stops(self):
        log = []
        steps = [make_step("a", log), make_step("b", log, problems=["b looks wrong"]), make_step("c", log)]
        self.assertFalse(run_steps(steps))
        self.assertEqual(log, ["a:action", "a:verify", "b:action", "b:verify"])  # c never ran.
        self.assertEqual([s.status for s in steps], [COMPLETED, FAILED, SKIPPED])
        self.assertEqual(steps[1].problems, ["b looks wrong"])
        self.assertEqual(steps[2].message, "Not run: step 2 failed.")

    def test_skipped_step_that_fails_verification_is_a_failure(self):
        steps = [make_step("a", [], raises=SkipStep("exists"), problems=["bad content"])]
        self.assertFalse(run_steps(steps))
        self.assertEqual((steps[0].status, steps[0].problems), (FAILED, ["bad content"]))

    def test_crashing_verification_is_a_failure(self):
        steps = [make_step("a", [], verify_raises=RuntimeError("boom")), make_step("b", [])]
        self.assertFalse(run_steps(steps))
        self.assertEqual(steps[0].status, FAILED)
        self.assertIn("Verification could not run (RuntimeError): boom", steps[0].problems[0])
        self.assertEqual(steps[1].status, SKIPPED)


class ExecutionFailureTest(unittest.TestCase):
    def test_step_error_stops_the_chain_and_skips_verification(self):
        log = []
        steps = [make_step("a", log, raises=StepError("disk is full")), make_step("b", log)]
        self.assertFalse(run_steps(steps))
        self.assertEqual(log, ["a:action"])  # No verification of a failed action, and b never ran.
        self.assertEqual((steps[0].status, steps[0].problems), (FAILED, ["disk is full"]))
        self.assertEqual((steps[1].status, steps[1].message), (SKIPPED, "Not run: step 1 failed."))

    def test_unexpected_exception_is_reported_not_raised(self):
        steps = [make_step("a", [], raises=PermissionError("denied"))]
        self.assertFalse(run_steps(steps))
        self.assertEqual(steps[0].problems, ["Unexpected error (PermissionError): denied"])

    def test_keyboard_interrupt_is_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            run_steps([make_step("a", [], raises=KeyboardInterrupt())])

    def test_failure_in_last_step(self):
        steps = [make_step("a", []), make_step("b", [], raises=StepError("nope"))]
        self.assertFalse(run_steps(steps))
        self.assertEqual([s.status for s in steps], [COMPLETED, FAILED])


class ReuseTest(unittest.TestCase):
    def test_a_finished_plan_cannot_be_run_again(self):
        log = []
        steps = [make_step("a", log)]
        run_steps(steps)
        with self.assertRaises(ValueError):
            run_steps(steps)
        self.assertEqual(log, ["a:action", "a:verify"])  # The action did not run a second time.


if __name__ == "__main__":
    unittest.main()
