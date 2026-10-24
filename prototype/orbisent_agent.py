"""Orbisent Prototype 0.3: turn a goal into verified files, step by step.

Orbisent — Beyond the Known.

This is a small, working version of the "Goal-to-Outcome" loop described in
VISION.md and Prototype.md:

    1. Accept a goal from the command line.
    2. Decide which task type the goal asks for (or use --task).
    3. Turn the task into ordered steps, each with an expected outcome.
    4. Show the plan and ask for permission.
    5. Run the steps one by one with the step engine (engine.py), verifying
       each step right after it runs and stopping at the first failure.
    6. Print an honest report of every step's status.

Supported task types:
    prepare_project          README.md, TASKS.md and LAUNCH_PLAN.md
    create_launch_checklist  LAUNCH_CHECKLIST.md

There is no AI model here yet. The task type is picked from keywords, and the
steps come from fixed rules, so the same goal always gives the same plan.
This is deterministic execution, not AI planning. It uses only Python's
standard library, needs no API keys or network, and it NEVER deletes or
overwrites files. If a file already exists, it is left untouched, reported as
"skipped", and still verified.

Examples:
    python3 prototype/orbisent_agent.py "Prepare my project folder for launch"
    python3 prototype/orbisent_agent.py "Create a launch checklist for my app"
    python3 prototype/orbisent_agent.py "Launch my bakery" --task create_launch_checklist
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from engine import COMPLETED, FAILED, PENDING, SKIPPED, SkipStep, Step, StepError, run_steps

DEFAULT_BASE_DIR = "orbisent_projects"

# Exit codes, so scripts (and tests) can tell what happened.
EXIT_SUCCESS = 0       # Every step was completed (or already done) and verified.
EXIT_INCOMPLETE = 1    # Cancelled, or a step failed (its action or its verification).
EXIT_UNCLASSIFIED = 2  # The goal could not be matched to one task type (argparse also uses 2).


# ---------------------------------------------------------------------------
# Task types: what Orbisent knows how to do
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileSpec:
    """One file a task creates, and the checks it must pass afterwards."""

    name: str                  # File name, e.g. "TASKS.md".
    build: object              # Function (goal, project_name) -> the file's text.
    title: str                 # The first line must start with this, e.g. "# Tasks".
    required: tuple = ()       # Pieces of text that must appear somewhere in the file.
    min_checkboxes: int = 0    # Minimum number of "- [ ] ..." items.
    min_numbered_steps: int = 0  # Minimum number of "1. ..." items.
    min_sections: int = 0      # Minimum number of "## ..." headings.


@dataclass(frozen=True)
class TaskType:
    """Everything Orbisent needs to know to carry out one kind of task."""

    identifier: str   # Used with --task, e.g. "prepare_project".
    description: str  # One line shown to the user.
    keywords: tuple   # Words or phrases in a goal that point to this task.
    plan: tuple       # The task-specific steps, in plain English.
    files: tuple      # The FileSpec for every file the task creates.


def readme_text(goal, project_name):
    return (
        f"# {project_name}\n\n"
        f"**Goal:** {goal}\n\n"
        f"Created by Orbisent Prototype 0.3 on {date.today().isoformat()}.\n\n"
        "## Files\n\n"
        "- `TASKS.md`: checklist of tasks to complete before launch.\n"
        "- `LAUNCH_PLAN.md`: the launch steps, in order.\n"
    )


def tasks_text(goal, project_name):
    return (
        "# Tasks\n\n"
        f"Goal: {goal}\n\n"
        "- [ ] Describe the project in one sentence in README.md\n"
        "- [ ] Decide who the project is for\n"
        "- [ ] List the features that must exist at launch\n"
        "- [ ] Test the project end to end\n"
        "- [ ] Prepare a launch announcement draft\n"
        "- [ ] Choose a launch date\n"
    )


def launch_plan_text(goal, project_name):
    return (
        "# Launch Plan\n\n"
        f"Goal: {goal}\n\n"
        "1. **Prepare:** finish the tasks in TASKS.md.\n"
        "2. **Check:** review the project and fix the problems you find.\n"
        "3. **Announce:** publish the announcement (only after you approve it).\n"
        "4. **Launch:** make the project available.\n"
        "5. **Review:** collect feedback and plan the next steps.\n"
    )


def launch_checklist_text(goal, project_name):
    return (
        "# Launch Checklist\n\n"
        f"Goal: {goal}\n\n"
        "Tick each box (`[x]`) when the item is done.\n\n"
        "## Before launch\n\n"
        "- [ ] Write a one-sentence description of what you are launching\n"
        "- [ ] Decide who it is for and what problem it solves\n"
        "- [ ] Pick a launch date and write it here: ____\n"
        "- [ ] List the must-have features and confirm each one works\n\n"
        "## Quality\n\n"
        "- [ ] Test the main flow yourself from start to finish\n"
        "- [ ] Ask at least one other person to try it and note their problems\n"
        "- [ ] Fix or write down every known bug\n"
        "- [ ] Check spelling, links and contact details\n\n"
        "## Communication\n\n"
        "- [ ] Draft the launch announcement\n"
        "- [ ] Choose where to announce it (website, email, social media)\n"
        "- [ ] Prepare answers to the questions people are likely to ask\n\n"
        "## Launch day\n\n"
        "- [ ] Make it available and check that it works for a new user\n"
        "- [ ] Publish the announcement (after you approve it)\n"
        "- [ ] Watch for problems and reply to early feedback\n\n"
        "## After launch\n\n"
        "- [ ] Collect feedback for one week\n"
        "- [ ] Write down what went well and what to improve\n"
        "- [ ] Plan the next step\n"
    )


TASK_TYPES = {
    "prepare_project": TaskType(
        identifier="prepare_project",
        description="Create a project folder with README.md, TASKS.md and LAUNCH_PLAN.md",
        keywords=("project folder", "project directory", "prepare my project", "prepare the project",
                  "prepare project", "set up my project", "set up a project", "setup project",
                  "new project", "scaffold"),
        plan=(
            "Write README.md with the project name, goal and a list of files",
            "Write TASKS.md with a checklist of tasks to finish before launch",
            "Write LAUNCH_PLAN.md with the launch steps in order",
        ),
        files=(
            FileSpec("README.md", readme_text, title="# ",
                     required=("**Goal:**", "## Files", "TASKS.md", "LAUNCH_PLAN.md")),
            FileSpec("TASKS.md", tasks_text, title="# Tasks", required=("Goal:",), min_checkboxes=5),
            FileSpec("LAUNCH_PLAN.md", launch_plan_text, title="# Launch Plan",
                     required=("Goal:",), min_numbered_steps=5),
        ),
    ),
    "create_launch_checklist": TaskType(
        identifier="create_launch_checklist",
        description="Create LAUNCH_CHECKLIST.md with actionable launch items",
        keywords=("checklist", "checklists", "check list"),
        plan=("Write LAUNCH_CHECKLIST.md with checkbox items grouped from preparation to after launch",),
        files=(
            FileSpec("LAUNCH_CHECKLIST.md", launch_checklist_text, title="# Launch Checklist",
                     required=("Goal:",), min_checkboxes=12, min_sections=4),
        ),
    ),
}


# ---------------------------------------------------------------------------
# Step 1: understand the goal
# ---------------------------------------------------------------------------

def clean_goal(text):
    """Collapse all whitespace (including newlines) so the goal fits on one line."""
    return " ".join(text.split())


def make_folder_name(text):
    """Turn any text into a safe folder name, e.g. "My App!" -> "my-app".

    Only letters, digits and dashes are kept, so names like "../secret" cannot
    escape the base folder.
    """
    name = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return name[:50].strip("-") or "project"


def classify_goal(goal):
    """Return the identifiers of every task type whose keywords appear in the goal.

    Keywords must match whole words: "checklist" matches "a checklist" but not
    "checklisting". Exactly one result means the goal is clear; none means
    unknown; more than one means ambiguous.
    """
    words = " " + re.sub(r"[^a-z0-9]+", " ", goal.lower()) + " "
    return [task_id for task_id, task in TASK_TYPES.items()
            if any(f" {keyword} " in words for keyword in task.keywords)]


# ---------------------------------------------------------------------------
# Step 2: checks used to verify files
# ---------------------------------------------------------------------------

def check_text(text, spec):
    """Return the problems found in one file's text (an empty list means it passed)."""
    if not text.strip():
        return ["Empty"]
    problems = []
    if not text.lstrip().startswith(spec.title):
        problems.append(f"Unexpected content (first line should start with {spec.title!r})")
    for piece in spec.required:
        if piece not in text:
            problems.append(f"Unexpected content (missing {piece!r})")
    for label, minimum, pattern in _counted_checks(spec):
        found = len(re.findall(pattern, text, flags=re.MULTILINE))
        if found < minimum:
            problems.append(f"Too few {label} (found {found}, expected at least {minimum})")
    return problems


def _counted_checks(spec):
    """The "at least N of these" checks of a FileSpec: (label, minimum, pattern)."""
    return (
        ("checkbox items", spec.min_checkboxes, r"^\s*- \[[ xX]\] \S"),
        ("numbered steps", spec.min_numbered_steps, r"^\s*\d+\. \S"),
        ("'## ' sections", spec.min_sections, r"^## \S"),
    )


def describe_checks(spec):
    """Explain a FileSpec's checks in words, for the plan's "Expected" line."""
    parts = [f"{spec.name} exists", f"its first line starts with {spec.title!r}"]
    if spec.required:
        parts.append("it contains " + ", ".join(repr(piece) for piece in spec.required))
    parts += [f"at least {minimum} {label}" for label, minimum, _ in _counted_checks(spec) if minimum]
    return "; ".join(parts)


def verify_file(path, spec=None):
    """Check one file: it must exist and be a file, and pass `spec`'s checks if given.

    Returns a list of problems. An empty list means the file is fine.
    """
    path = Path(path)
    if not path.exists():
        return [f"Missing: {path}"]
    if not path.is_file():
        return [f"Not a file: {path}"]
    if spec is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [f"Could not read {path}: {error}"]
    return [f"{problem}: {path}" for problem in check_text(text, spec)]


def verify_files(project_dir, task):
    """Check every file the task should have created. Returns a list of problems."""
    problems = []
    for spec in task.files:
        problems.extend(verify_file(Path(project_dir) / spec.name, spec))
    return problems


# ---------------------------------------------------------------------------
# Step 3: turn the task into steps, each with an action and a verification
# ---------------------------------------------------------------------------

def build_contents(task, goal, project_name):
    """Return {file name: text} for every file the task will create."""
    return {spec.name: spec.build(goal, project_name) for spec in task.files}


def folder_step(project_dir):
    """A step that creates the project folder, or reuses it if it already exists."""

    def action():
        if project_dir.is_dir():
            raise SkipStep(f"Folder already exists, reusing it: {project_dir}")
        try:
            project_dir.mkdir(parents=True)
        except OSError as error:
            raise StepError(f"Could not create folder {project_dir}: {error}")
        return f"Created folder: {project_dir}"

    def verify():
        return [] if project_dir.is_dir() else [f"Not a folder: {project_dir}"]

    return Step(f"Create the project folder {project_dir} (reused if it already exists)",
                f"{project_dir} exists and is a folder", action, verify)


def file_step(path, text, description, spec=None):
    """A step that creates one new file. It never overwrites: an existing file is skipped."""

    def action():
        try:
            # Mode "x" means "create a new file; fail if it already exists".
            # This is what guarantees we never overwrite an existing file.
            with open(path, "x", encoding="utf-8") as f:
                f.write(text)
        except FileExistsError:
            raise SkipStep(f"File already exists, left unchanged: {path}")
        except OSError as error:
            raise StepError(f"Could not create {path}: {error}")
        return f"Created file: {path}"

    expected = describe_checks(spec) if spec else f"{path.name} exists and is a file"
    return Step(description, expected, action, lambda: verify_file(path, spec))


def build_steps(task, goal, project_dir, project_name):
    """The full plan for a task: create the folder, then one step per file.

    Each file step uses the task's own plan sentence as its description, so a
    task type needs exactly one plan sentence per file.
    """
    if len(task.plan) != len(task.files):
        raise ValueError(f"{task.identifier}: needs one plan step per file")
    contents = build_contents(task, goal, project_name)
    return [folder_step(project_dir)] + [
        file_step(project_dir / spec.name, contents[spec.name], description, spec)
        for description, spec in zip(task.plan, task.files)
    ]


def create_project(project_dir, contents):
    """Create the folder and the given files, checking only that each file exists.

    Kept from Prototype 0.2 as a simple building block. Unlike the full plan,
    it tries every file even if an earlier file fails. It never deletes or
    overwrites anything. Returns (completed, skipped, errors), lists of messages.
    """
    folder = folder_step(project_dir)
    steps = [folder]
    if run_steps([folder]):  # Without the folder, no file can be created.
        for name, text in contents.items():
            step = file_step(project_dir / name, text, f"Create {name}")
            run_steps([step])
            steps.append(step)
    completed = [step.message for step in steps if step.status == COMPLETED]
    skipped = [step.message for step in steps if step.status == SKIPPED]
    errors = [problem for step in steps if step.status == FAILED for problem in step.problems]
    return completed, skipped, errors


# ---------------------------------------------------------------------------
# Step 4: show the plan, and report what actually happened
# ---------------------------------------------------------------------------

def print_plan(task, steps):
    print(f"\nPlan:\n  (fixed steps for {task.identifier}, written by rules, not by an AI)")
    for number, step in enumerate(steps, start=1):
        print(f"  {number}. {step.description}")
        print(f"     Expected: {step.expected}")
    print("Files are only created, never overwritten or deleted. "
          "Every step is verified, and execution stops at the first failed step.")


def print_report(steps, success):
    """Print every step's status. The report only states what actually happened."""
    print("\n=== Orbisent report ===\n")
    for number, step in enumerate(steps, start=1):
        print(f"  {number}. [{step.status}] {step.description}")
        if step.message:
            print(f"       Result:  {step.message}")
        for problem in step.problems:
            print(f"       Problem: {problem}")
    counts = {status: sum(step.status == status for step in steps)
              for status in (COMPLETED, SKIPPED, FAILED, PENDING)}
    print("\nSteps: " + ", ".join(f"{count} {status}" for status, count in counts.items() if count))
    if success:
        print("Result: SUCCESS: every step was completed (or already done) and verified.")
    else:
        failed = next(number for number, step in enumerate(steps, start=1) if step.status == FAILED)
        later = ", so the steps after it were not run" if failed < len(steps) else ""
        print(f"Result: INCOMPLETE: step {failed} failed{later}.")


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def ask_permission(input_func=input):
    """Ask the user to approve the plan. Anything other than "y"/"yes" means no."""
    try:
        answer = input_func("\nProceed with this plan? [y/N] ")
    except EOFError:  # No keyboard input available (e.g. running in a script).
        return False
    return answer.strip().lower() in ("y", "yes")


def explain_unclassified(goal, matches):
    """Tell the user why no task was chosen, and how to choose one."""
    if matches:
        print(f"Could not classify the goal: it matches more than one task type ({', '.join(matches)}).")
    else:
        print("Could not classify the goal: it does not match any task type Orbisent knows.")
    print("Nothing was created. Choose a task type with --task, for example:")
    for task in TASK_TYPES.values():
        print(f'  --task {task.identifier:24s} {task.description}')
    print(f'\n  python3 prototype/orbisent_agent.py "{goal}" --task prepare_project')


def main(argv=None, input_func=input):
    parser = argparse.ArgumentParser(
        description="Orbisent Prototype 0.3: turn a goal into verified files, step by step.")
    parser.add_argument("goal", help='Your goal, e.g. "Prepare my project folder for launch"')
    parser.add_argument("--task", choices=list(TASK_TYPES),
                        help="Choose the task type yourself instead of letting Orbisent pick it")
    parser.add_argument("--name", help="Project folder name (default: made from the goal)")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR,
                        help=f"Where project folders are created (default: ./{DEFAULT_BASE_DIR})")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation question")
    args = parser.parse_args(argv)

    goal = clean_goal(args.goal)
    if not goal:
        parser.error("the goal must not be empty")

    print(f"Orbisent — Beyond the Known.\n\nGoal: {goal}")

    # An explicit --task always wins; otherwise pick from keywords, but never guess.
    if args.task:
        task = TASK_TYPES[args.task]
        reason = "chosen with --task"
    else:
        matches = classify_goal(goal)
        if len(matches) != 1:
            explain_unclassified(goal, matches)
            return EXIT_UNCLASSIFIED
        task = TASK_TYPES[matches[0]]
        reason = "chosen from keywords in the goal"

    project_name = make_folder_name(args.name or goal)
    project_dir = Path(args.base_dir) / project_name

    print(f"Task type: {task.identifier} ({reason})\n  {task.description}")
    steps = build_steps(task, goal, project_dir, project_name)
    print_plan(task, steps)

    if not args.yes and not ask_permission(input_func):
        print("Cancelled. Nothing was changed.")
        return EXIT_INCOMPLETE

    success = run_steps(steps)
    print_report(steps, success)
    return EXIT_SUCCESS if success else EXIT_INCOMPLETE


if __name__ == "__main__":
    sys.exit(main())
