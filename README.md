# Orbisent
Beyond the Known.

Orbisent is an early-stage project to build a personal AI agent that turns a person's goals into planned,
executed and **verified** results, and reports honestly what worked and what didn't.
The long-term vision is in [`VISION.md`](VISION.md); the first prototype's scope is in [`Prototype.md`](Prototype.md).

## Current state: Prototype 0.2

[`prototype/`](prototype/) contains a small command-line program, using only the Python standard library.
It takes a goal, picks a task type from fixed keywords, shows a plan and asks for permission.
Then it creates the files, verifies them and prints a report. It never overwrites or deletes files.

| Task type | Creates |
| --- | --- |
| `prepare_project` | `README.md`, `TASKS.md`, `LAUNCH_PLAN.md` |
| `create_launch_checklist` | `LAUNCH_CHECKLIST.md` |

```bash
python3 prototype/orbisent_agent.py "Prepare my project folder for launch"
python3 prototype/orbisent_agent.py "Create a launch checklist for my app"
python3 -m unittest discover -s prototype -v   # run the tests
```

See [`prototype/README.md`](prototype/README.md) for all options, safety rules and a Google Colab option.

The repository also contains [`notebooks/01_train_from_scratch.ipynb`](notebooks/01_train_from_scratch.ipynb),
an experiment that trains a tiny character-level language model from random weights in Google Colab.
It is separate from the prototype.

## Limitations

Orbisent is **not** a fully autonomous AI agent yet. The prototype doesn't use an AI model.
It recognises goals by keywords, supports two task types with fixed templates, and only creates local files.
It has no memory, integrations, voice control or scheduling.
