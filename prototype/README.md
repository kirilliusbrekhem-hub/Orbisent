# Orbisent Prototype 0.2

*Beyond the Known.*

A small working version of Orbisent's Goal-to-Outcome loop (see [`../VISION.md`](../VISION.md) and
[`../Prototype.md`](../Prototype.md)). You give it a goal and it:

1. picks a **task type** from keywords in the goal (or uses the one you choose with `--task`),
2. shows a step-by-step plan and asks for your permission,
3. creates the task's files inside a project folder,
4. checks that every file exists and has the expected structure,
5. prints a report of completed actions, skipped items and errors.

It uses only Python's standard library (tested with Python 3.13) and needs no API keys or paid services.
Task selection and plans come from fixed rules; no AI model is involved yet.

## Task types

| Task type | Picked when the goal mentions | Creates | Checked for |
| --- | --- | --- | --- |
| `prepare_project` | "project folder", "prepare my project", "set up a project", "new project", "scaffold", … | `README.md`, `TASKS.md`, `LAUNCH_PLAN.md` | README: title, `**Goal:**`, `## Files` and both file names. TASKS: `# Tasks` title and at least 5 checkboxes. LAUNCH_PLAN: `# Launch Plan` title and at least 5 numbered steps. |
| `create_launch_checklist` | "checklist", "check list" | `LAUNCH_CHECKLIST.md` | `# Launch Checklist` title, the goal, at least 4 `## ` sections and at least 12 checkboxes. |

The keywords are listed in `TASK_TYPES` in `orbisent_agent.py`. If a goal matches **no** task type, or
**more than one**, Orbisent explains why, creates nothing, and asks you to choose with `--task`.
An explicit `--task` always wins over the keywords.

To add a task type, add a `TaskType` entry to `TASK_TYPES`. It needs an identifier, a description, keywords,
plan steps and a `FileSpec` (file name, text builder and checks) for each file.

## Safety

- **Never deletes or overwrites files.** Files are opened in "create only" mode. If a file already exists,
  it is left unchanged and reported as *skipped*, so running the same goal twice is safe.
- Folder names are cleaned to letters, digits and dashes, so `--name ../../x` can't write outside the base folder.
- The plan is always shown first. Nothing happens until you answer `y`, unless you pass `--yes`.
- Unknown or ambiguous goals create nothing. An unsupported `--task` value is rejected before anything runs.
- Folder and file errors (for example a missing permission) are reported, never hidden.

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
```

Projects are created in `orbisent_projects/<folder-name>/`, which git ignores.

| Option | Meaning |
| --- | --- |
| `--task TYPE` | `prepare_project` or `create_launch_checklist`; overrides automatic selection |
| `--name NAME` | Choose the project folder name instead of deriving it from the goal |
| `--base-dir DIR` | Create projects inside `DIR` (default: `orbisent_projects`) |
| `--yes` | Skip the confirmation question |

Exit codes: `0` means everything was created and verified. `1` means it was cancelled, or something failed
or didn't verify. `2` means the goal couldn't be classified or the arguments were invalid.

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

- Task types are picked by keyword matching, not by understanding the goal. Rephrasing can change the result
  or make the goal unclassifiable; use `--task` when that happens.
- Only two task types, each with fixed document templates. Only the goal and folder name change.
- The checks confirm structure (titles, sections, checkboxes, steps), not the quality of the writing.
- When a file already exists, it is checked as it is. If you've edited it, it may no longer pass.
- No memory, integrations or AI model yet.
