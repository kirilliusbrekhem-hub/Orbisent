# Orbisent Prototype 0.1

*Beyond the Known.*

The smallest working version of Orbisent's Goal-to-Outcome loop (see [`../VISION.md`](../VISION.md) and
[`../Prototype.md`](../Prototype.md)). You give it a goal and it:

1. creates a step-by-step plan and shows it to you,
2. asks for your permission,
3. creates a project folder containing `README.md`, `TASKS.md` and `LAUNCH_PLAN.md`,
4. verifies that every file exists, isn't empty and has the expected heading,
5. prints a report of completed actions, skipped items and errors.

It uses only Python's standard library (Python 3.8 or newer) and needs no API keys or paid services.
The plan comes from simple rules; no AI model is involved yet.

## Safety

- **Never deletes or overwrites files.** Files are opened in "create only" mode. If a file already exists,
  it is left unchanged and reported as *skipped*, so running the same goal twice is safe.
- Folder names are cleaned to letters, digits and dashes, so a goal like `../../x` can't write outside the base folder.
- Nothing happens until you answer `y`, unless you pass `--yes`.
- The program exits with code `0` only when every expected file was verified.

## How to run the prototype

From the repository root:

```bash
python3 prototype/orbisent_agent.py "Prepare my project folder for launch"
```

This creates `orbisent_projects/prepare-my-project-folder-for-launch/` (ignored by git).

Options:

| Option | Meaning |
| --- | --- |
| `--name NAME` | Choose the project folder name instead of deriving it from the goal |
| `--base-dir DIR` | Create projects inside `DIR` (default: `orbisent_projects`) |
| `--yes` | Skip the confirmation question |

Example without the confirmation question:

```bash
python3 prototype/orbisent_agent.py "Launch my bakery website" --name bakery --yes
```

No local Python? Run it in a free [Google Colab](https://colab.research.google.com) notebook cell:

```
!git clone https://github.com/kirilliusbrekhem-hub/Orbisent.git
%cd Orbisent
!python3 prototype/orbisent_agent.py "Prepare my project folder for launch" --yes
```

(A private repository needs a GitHub token to clone in Colab.)

## Running the tests

```bash
python3 -m unittest discover -s prototype -v
```

## Limitations

This is a local experiment: a fixed set of three documents, a rule-based plan and no memory or integrations.
