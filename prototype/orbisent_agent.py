"""Orbisent Prototype 0.1: turn a goal into a verified project folder.

Orbisent — Beyond the Known.

This is the smallest working version of the "Goal-to-Outcome" loop described in
VISION.md and Prototype.md:

    1. Accept a goal from the command line.
    2. Create a step-by-step plan.
    3. Show the plan and ask for permission.
    4. Create a project folder with README.md, TASKS.md and LAUNCH_PLAN.md.
    5. Verify that every expected file exists and has the expected content.
    6. Print an honest report of what was done and what went wrong.

There is no AI model here yet: the plan is built from simple, predictable rules.
It uses only Python's standard library, needs no API keys, and it NEVER deletes
or overwrites files. If a file already exists, it is left untouched and reported
as "skipped".

Example:
    python3 prototype/orbisent_agent.py "Prepare my project folder for launch"
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

# The files every project folder must contain, and a line each file must include.
# The verifier uses the line to check that the file holds what we expect.
EXPECTED_FILES = {
    "README.md": "# ",
    "TASKS.md": "# Tasks",
    "LAUNCH_PLAN.md": "# Launch Plan",
}

DEFAULT_BASE_DIR = "orbisent_projects"


# ---------------------------------------------------------------------------
# Step 1: understand the goal
# ---------------------------------------------------------------------------

def make_folder_name(text):
    """Turn any text into a safe folder name, e.g. "My App!" -> "my-app".

    Only letters, digits and dashes are kept, so names like "../secret" cannot
    escape the base folder.
    """
    name = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return name[:50].strip("-") or "project"


# ---------------------------------------------------------------------------
# Step 2: make a plan
# ---------------------------------------------------------------------------

def build_file_contents(goal, project_name):
    """Return {file name: text} for the documents we will create."""
    today = date.today().isoformat()
    return {
        "README.md": (
            f"# {project_name}\n\n"
            f"**Goal:** {goal}\n\n"
            f"Created by Orbisent Prototype 0.1 on {today}.\n\n"
            "## Files\n\n"
            "- `TASKS.md`: checklist of tasks to complete before launch.\n"
            "- `LAUNCH_PLAN.md`: the launch steps, in order.\n"
        ),
        "TASKS.md": (
            "# Tasks\n\n"
            f"Goal: {goal}\n\n"
            "- [ ] Describe the project in one sentence in README.md\n"
            "- [ ] Decide who the project is for\n"
            "- [ ] List the features that must exist at launch\n"
            "- [ ] Test the project end to end\n"
            "- [ ] Prepare a launch announcement draft\n"
            "- [ ] Choose a launch date\n"
        ),
        "LAUNCH_PLAN.md": (
            "# Launch Plan\n\n"
            f"Goal: {goal}\n\n"
            "1. **Prepare:** finish the tasks in TASKS.md.\n"
            "2. **Check:** review the project and fix the problems you find.\n"
            "3. **Announce:** publish the announcement (only after you approve it).\n"
            "4. **Launch:** make the project available.\n"
            "5. **Review:** collect feedback and plan the next steps.\n"
        ),
    }


def make_plan(goal, project_dir):
    """Return the plan as a list of plain-English steps.

    Each step is a dictionary so it is easy to print now and to extend later.
    """
    steps = [{"action": "create_folder", "path": project_dir,
              "description": f"Create the project folder {project_dir}"}]
    for file_name in EXPECTED_FILES:
        steps.append({"action": "create_file", "path": project_dir / file_name,
                      "description": f"Create {file_name} (skipped if it already exists)"})
    steps.append({"action": "verify", "path": project_dir,
                  "description": "Verify that all expected files exist and have the right content"})
    steps.append({"action": "report", "path": None,
                  "description": "Report completed actions and any errors"})
    return steps


# ---------------------------------------------------------------------------
# Step 3: act (safely)
# ---------------------------------------------------------------------------

def create_project(project_dir, contents):
    """Create the folder and files. Never deletes or overwrites anything.

    Returns (completed, skipped, errors), three lists of messages.
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

def verify_files(project_dir, expected=EXPECTED_FILES):
    """Check every expected file: it must exist, be a file, not be empty,
    and contain its expected line.

    Returns a list of problems. An empty list means everything is fine.
    """
    problems = []
    for file_name, required_text in expected.items():
        path = Path(project_dir) / file_name
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
            if not text.strip():
                problems.append(f"Empty: {path}")
            elif required_text not in text:
                problems.append(f"Unexpected content in {path} (expected {required_text!r})")
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

def ask_permission():
    """Ask the user to approve the plan. Anything other than "y"/"yes" means no."""
    try:
        answer = input("\nProceed with this plan? [y/N] ")
    except EOFError:  # No keyboard input available (e.g. running in a script).
        return False
    return answer.strip().lower() in ("y", "yes")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Orbisent Prototype 0.1: turn a goal into a verified project folder.")
    parser.add_argument("goal", help='Your goal, e.g. "Prepare my project folder for launch"')
    parser.add_argument("--name", help="Project folder name (default: made from the goal)")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR,
                        help=f"Where project folders are created (default: ./{DEFAULT_BASE_DIR})")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation question")
    args = parser.parse_args(argv)

    goal = args.goal.strip()
    if not goal:
        parser.error("the goal must not be empty")

    project_name = make_folder_name(args.name or goal)
    project_dir = Path(args.base_dir) / project_name

    print(f"Orbisent — Beyond the Known.\n\nGoal: {goal}\n\nPlan:")
    plan = make_plan(goal, project_dir)
    for number, step in enumerate(plan, start=1):
        print(f"  {number}. {step['description']}")

    if not args.yes and not ask_permission():
        print("Cancelled. Nothing was changed.")
        return 1

    completed, skipped, errors = create_project(project_dir, build_file_contents(goal, project_name))
    problems = verify_files(project_dir)
    success = print_report(completed, skipped, errors, problems)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
