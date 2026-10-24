"""Orbisent step engine: run a fixed list of steps in order and verify each one.

Orbisent — Beyond the Known.

This engine is deterministic: it runs exactly the steps it is given, in the
order given. It does not plan, guess or call any AI model or network service.

How a step runs:

    1. Its action runs. The action may:
         - return a message      -> the step did its work ("completed")
         - raise SkipStep(msg)   -> nothing needed doing ("skipped")
         - raise any exception   -> the action failed ("failed")
    2. Its verify function ALWAYS runs afterwards (also for skipped steps) and
       returns a list of problems. Any problem makes the step "failed".
    3. After a failed step, every later step is marked "skipped" and its action
       is never called.

Example:
    steps = [Step("Say hello", "Nothing changes", action=lambda: "Hello", verify=lambda: [])]
    ok = run_steps(steps)   # True; steps[0].status == COMPLETED
"""

from dataclasses import dataclass, field

# The four states a step can be in.
PENDING = "pending"      # Not run yet.
COMPLETED = "completed"  # The action did its work and verification passed.
SKIPPED = "skipped"      # Nothing needed doing (verified), or not run because an earlier step failed.
FAILED = "failed"        # The action or its verification failed.


class SkipStep(Exception):
    """Raised by an action when there is nothing to do (for example, the file already exists)."""


class StepError(Exception):
    """Raised by an action to report a failure with a clear, user-friendly message."""


@dataclass
class Step:
    """One step of a plan, plus what happened when it ran."""

    description: str  # What the step does, shown in the plan.
    expected: str     # The outcome verification will check, shown in the plan.
    action: object    # Function with no arguments; returns a short message.
    verify: object    # Function with no arguments; returns a list of problems ([] = passed).
    status: str = PENDING
    message: str = ""  # What the action reported, or why the step did not run.
    problems: list = field(default_factory=list)  # Verification problems or the error.


def run_steps(steps):
    """Run the steps in order, stopping at the first failure.

    Every step's status, message and problems are filled in. Returns True only
    if no step failed.
    """
    if any(step.status != PENDING for step in steps):
        raise ValueError("Every step must be pending; build a fresh plan to run it again.")

    for number, step in enumerate(steps, start=1):
        _run_one(step)
        if step.status == FAILED:
            for later in steps[number:]:
                later.status = SKIPPED
                later.message = f"Not run: step {number} failed."
            return False
    return True


def _run_one(step):
    """Run one step's action, then its verification, and record the result."""
    try:
        step.message = step.action()
        step.status = COMPLETED
    except SkipStep as reason:
        step.message = str(reason)
        step.status = SKIPPED
    except StepError as error:
        _fail(step, str(error))
        return
    except Exception as error:  # A bug or an unexpected problem: report it, don't crash.
        _fail(step, f"Unexpected error ({type(error).__name__}): {error}")
        return

    try:
        problems = list(step.verify())
    except Exception as error:
        problems = [f"Verification could not run ({type(error).__name__}): {error}"]
    if problems:
        step.status = FAILED
        step.problems = problems


def _fail(step, problem):
    step.status = FAILED
    step.problems = [problem]
