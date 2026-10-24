# Orbisent Prototype 0.3

*Beyond the Known.*

A small working version of Orbisent's Goal-to-Outcome loop (see [`../VISION.md`](../VISION.md) and
[`../Prototype.md`](../Prototype.md)). You give it a goal and it:

1. picks a **task type** from keywords in the goal (or uses the one you choose with `--task`),
2. turns the task into **ordered steps**, each with a description and an **expected outcome**,
3. shows that plan and asks for your permission,
4. runs the steps one at a time, **verifying each step right after it runs** and **stopping at the first failure**,
5. prints a report with every step's status: `completed`, `skipped` or `failed`.

It uses only Python's standard library (tested with Python 3.13) and needs no API keys, network or paid services.

**This is deterministic execution, not AI planning.** The task type comes from keyword matching, and the
steps are fixed rules written in the code. The same goal always gives the same plan. No AI model is involved yet.

## Task types

| Task type | Picked when the goal mentions | Creates | Checked for |
| --- | --- | --- | --- |
| `prepare_project` | "project folder", "prepare my project", "set up a project", "new project", "scaffold", … | `README.md`, `TASKS.md`, `LAUNCH_PLAN.md` | README: title, `**Goal:**`, `## Files` and both file names. TASKS: `# Tasks` title and at least 5 checkboxes. LAUNCH_PLAN: `# Launch Plan` title and at least 5 numbered steps. |
| `create_launch_checklist` | "checklist", "check list" | `LAUNCH_CHECKLIST.md` | `# Launch Checklist` title, the goal, at least 4 `## ` sections and at least 12 checkboxes. |

The keywords are listed in `TASK_TYPES` in `orbisent_agent.py`. If a goal matches **no** task type, or
**more than one**, Orbisent explains why, creates nothing, and asks you to choose with `--task`.
An explicit `--task` always wins over the keywords.

To add a task type, add a `TaskType` entry to `TASK_TYPES`. It needs an identifier, a description, keywords,
exactly one plan sentence per file, and a `FileSpec` (file name, text builder and checks) for each file.

## How steps run (Prototype 0.3)

The step engine is in [`engine.py`](engine.py). It knows nothing about files: it runs whatever steps it's given.

Each step has a description, an expected outcome, an **action** and a **verification**. For each step, in order:

1. The action runs.
   - If it does its work, the step is `completed`.
   - If there's nothing to do (the folder or file already exists), the step is `skipped`, and nothing is changed.
   - If it fails (for example, permission denied), the step is `failed`.
2. The verification runs, even for skipped steps. If any check fails, the step becomes `failed`.
   A step that already existed but has the wrong content is never reported as a success.
3. After a failed step, every later step is marked `skipped` with "Not run: step N failed", and its action never runs.

Every step starts as `pending`. The run succeeds only if no step failed.

A `prepare_project` plan has 4 steps: create the folder, then one step per file. A `create_launch_checklist` plan has 2.

**Change from 0.2:** a failed step now stops the remaining steps. In 0.2, the other files were still created.

## Safety

- **Never deletes or overwrites files.** Files are opened in "create only" mode. If a file already exists,
  it is left unchanged and reported as *skipped*, so running the same goal twice is safe.
- Folder names are cleaned to letters, digits and dashes, so `--name ../../x` can't write outside the base folder.
- The plan is always shown first. Nothing happens until you answer `y`, unless you pass `--yes`.
- Unknown or ambiguous goals create nothing. An unsupported `--task` value is rejected before anything runs.
- Folder and file errors (for example a missing permission) are reported, never hidden.
- Every action is a local folder or file creation shown in the plan. There are no network calls,
  deletions or hidden actions.

## How to run the prototype

From the repository root:

```bash
# prepare_project, picked automatically
python3 prototype/orbisent_agent.py "Prepare my project folder for launch"

# create_launch_checklist, picked automatically
python3 prototype/orbisent_agent.py "Create a launch checklist for my app"

# choose the task type yourself, with your own folder name, and skip the question
python3 prototype/orbisent_agent.py "Launch my bakery website" --task create_launch_checklist --name bakery --yes

# an unclear goal: Orbisent explains that it can't classify it and creates nothing
python3 prototype/orbisent_agent.py "Make me a sandwich"

# see a verification failure: an existing file with the wrong content is left alone,
# the step fails, and the run stops (exit code 1)
mkdir -p orbisent_projects/broken && echo "hello" > orbisent_projects/broken/TASKS.md
python3 prototype/orbisent_agent.py "Prepare my project folder" --name broken --yes
```

A report looks like this (paths shortened):

```
=== Orbisent report ===

  1. [skipped] Create the project folder orbisent_projects/broken (reused if it already exists)
       Result:  Folder already exists, reusing it: orbisent_projects/broken
  2. [completed] Write README.md with the project name, goal and a list of files
       Result:  Created file: orbisent_projects/broken/README.md
  3. [failed] Write TASKS.md with a checklist of tasks to finish before launch
       Result:  File already exists, left unchanged: orbisent_projects/broken/TASKS.md
       Problem: Unexpected content (first line should start with '# Tasks'): orbisent_projects/broken/TASKS.md
       ...
  4. [skipped] Write LAUNCH_PLAN.md with the launch steps in order
       Result:  Not run: step 3 failed.

Steps: 1 completed, 2 skipped, 1 failed
Result: INCOMPLETE: step 3 failed, so the steps after it were not run.
```

Projects are created in `orbisent_projects/<folder-name>/`, which git ignores.

| Option | Meaning |
| --- | --- |
| `--task TYPE` | `prepare_project` or `create_launch_checklist`; overrides automatic selection |
| `--name NAME` | Choose the project folder name instead of deriving it from the goal |
| `--base-dir DIR` | Create projects inside `DIR` (default: `orbisent_projects`) |
| `--yes` | Skip the confirmation question |

Exit codes: `0` means every step was completed (or already done) and verified. `1` means it was cancelled,
or a step failed. `2` means the goal couldn't be classified or the arguments were invalid.

No local Python? Run it in a free [Google Colab](https://colab.research.google.com) notebook cell:

```
!git clone https://github.com/kirilliusbrekhem-hub/Orbisent.git
%cd Orbisent
!python3 prototype/orbisent_agent.py "Create a launch checklist for my app" --yes
```

(A private repository needs a GitHub token to clone in Colab.)

## Running the tests

```bash
python3 -m unittest discover -s prototype -v
```

## Limitations

- **No AI planning.** Steps aren't generated from the goal. They're fixed per task type, and the engine only runs them.
- The only actions are "create a folder" and "create a new file". There's no editing, moving, network access
  or calling of other programs.
- There's no retry or automatic repair. A failed step stops the run, and you fix the cause and run it again.
  Steps that already succeeded are then skipped and verified again.
- Stopping on failure doesn't undo earlier steps. Files created before the failure stay, because nothing is ever deleted.

- Task types are picked by keyword matching, not by understanding the goal. Rephrasing can change the result
  or make the goal unclassifiable; use `--task` when that happens.
- Only two task types, each with fixed document templates. Only the goal and folder name change.
- The checks confirm structure (titles, sections, checkboxes, steps), not the quality of the writing.
- When a file already exists, it is checked as it is. If you've edited it, it may no longer pass.
- No memory, integrations or AI model yet. Orbisent is not an autonomous AI agent.
