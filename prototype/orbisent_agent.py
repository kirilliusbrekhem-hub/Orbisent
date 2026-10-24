"""Orbisent Prototype 0.2: turn a goal into verified files, using task types.

Orbisent — Beyond the Known.

This is a small, working version of the "Goal-to-Outcome" loop described in
VISION.md and Prototype.md:

    1. Accept a goal from the command line.
    2. Decide which task type the goal asks for (or use --task).
    3. Create a step-by-step plan, show it, and ask for permission.
    4. Create the task's files inside a project folder.
    5. Verify that every expected file exists and has the expected content.
    6. Print an honest report of what was done and what went wrong.

Supported task types:
    prepare_project          README.md, TASKS.md and LAUNCH_PLAN.md
    create_launch_checklist  LAUNCH_CHECKLIST.md

There is no AI model here yet: the task type is picked from keywords and the
plan comes from fixed rules, so the same goal always gives the same result.
It uses only Python's standard library, needs no API keys, and it NEVER deletes
or overwrites files. If a file already exists, it is left untouched and reported
as "skipped".

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

DEFAULT_BASE_DIR = "orbisent_projects"

# Exit codes, so scripts (and tests) can tell what happened.
EXIT_SUCCESS = 0       # Everything was created and verified.
EXIT_INCOMPLETE = 1    # Cancelled, or something failed or did not verify.
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
        f"Created by Orbisent Prototype 0.2 on {date.today().isoformat()}.\n\n"
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
# Step 2: make a plan
# ---------------------------------------------------------------------------

def make_plan(task, project_dir):
    """Return the plan as a list of plain-English steps."""
    return (
        [f"Create the project folder {project_dir} (reused if it already exists)"]
        + list(task.plan)
        + ["Skip any file that already exists, so nothing is overwritten",
           "Verify that every file exists and has the expected content",
           "Report completed actions, skipped items and errors"]
    )


def build_contents(task, goal, project_name):
    """Return {file name: text} for every file the task will create."""
    return {spec.name: spec.build(goal, project_name) for spec in task.files}


# ---------------------------------------------------------------------------
# Step 3: act (safely)
# ---------------------------------------------------------------------------

def create_project(project_dir, contents):
    """Create the folder and files. Never deletes or overwrites anything.

    `contents` is {file name: text}. Returns (completed, skipped, errors),
    three lists of messages.
    """
    completed, skipped, errors = [], [], []

    try:
        if project_dir.is_dir():
            skipped.append(f"Folder already exists, reusing it: {project_dir}")
        else:
            project_dir.mkdir(parents=True)
            completed.append(f"Created folder: {project_dir}")
    except OSError as error:
        errors.append(f"Could not create folder {project_dir}: {error}")
        return completed, skipped, errors  # Without the folder, no file can be created.

    for file_name, text in contents.items():
        path = project_dir / file_name
        try:
            # Mode "x" means "create a new file; fail if it already exists".
            # This is what guarantees we never overwrite an existing file.
            with open(path, "x", encoding="utf-8") as f:
                f.write(text)
            completed.append(f"Created file: {path}")
        except FileExistsError:
            skipped.append(f"File already exists, left unchanged: {path}")
        except OSError as error:
            errors.append(f"Could not create {path}: {error}")

    return completed, skipped, errors


# ---------------------------------------------------------------------------
# Step 4: verify
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
    counts = (
        ("checkbox items", spec.min_checkboxes, r"^\s*- \[[ xX]\] \S"),
        ("numbered steps", spec.min_numbered_steps, r"^\s*\d+\. \S"),
        ("'## ' sections", spec.min_sections, r"^## \S"),
    )
    for label, minimum, pattern in counts:
        found = len(re.findall(pattern, text, flags=re.MULTILINE))
        if found < minimum:
            problems.append(f"Too few {label} (found {found}, expected at least {minimum})")
    return problems


def verify_files(project_dir, task):
    """Check every file the task should have created.

    Returns a list of problems. An empty list means everything is fine.
    """
    problems = []
    for spec in task.files:
        path = Path(project_dir) / spec.name
        if not path.exists():
            problems.append(f"Missing: {path}")
        elif not path.is_file():
            problems.append(f"Not a file: {path}")
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                problems.append(f"Could not read {path}: {error}")
                continue
            problems.extend(f"{problem}: {path}" for problem in check_text(text, spec))
    return problems


# ---------------------------------------------------------------------------
# Step 5: report
# ---------------------------------------------------------------------------

def print_report(completed, skipped, errors, problems):
    """Print what happened. The report only states what actually occurred."""
    print("\n=== Orbisent report ===")
    for title, items in (("Completed", completed), ("Skipped", skipped),
                         ("Errors", errors), ("Verification problems", problems)):
        print(f"\n{title}:")
        print("\n".join(f"  - {item}" for item in items) if items else "  (none)")
    success = not errors and not problems
    print("\nResult:", "SUCCESS: all expected files verified." if success
          else "INCOMPLETE: see the errors above.")
    return success


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
        description="Orbisent Prototype 0.2: turn a goal into verified files.")
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

    print(f"Task type: {task.identifier} ({reason})\n  {task.description}\n\nPlan:")
    for number, step in enumerate(make_plan(task, project_dir), start=1):
        print(f"  {number}. {step}")

    if not args.yes and not ask_permission(input_func):
        print("Cancelled. Nothing was changed.")
        return EXIT_INCOMPLETE

    completed, skipped, errors = create_project(project_dir, build_contents(task, goal, project_name))
    problems = verify_files(project_dir, task)
    success = print_report(completed, skipped, errors, problems)
    return EXIT_SUCCESS if success else EXIT_INCOMPLETE


if __name__ == "__main__":
    sys.exit(main())
