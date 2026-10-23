# Orbisent — Prototype 0.1

## Goal
Build an AI agent that turns a user's goal into completed, verified results.

## First scenario
User request: "Prepare my project folder for launch."

## Expected behavior
1. Understand the user's goal.
2. Create a clear execution plan.
3. Ask for permission when necessary.
4. Create the project folder and subfolders.
5. Generate a README, task checklist, and launch plan.
6. Verify that all files exist and contain the expected content.
7. Report completed actions, errors, and remaining tasks.

## Initial tools
- File and folder creation
- Text file editing
- Task planning
- Result verification
- Execution log

## Safety
- Never delete or overwrite files without permission.
- Never send messages or publish content without confirmation.
- Show the user what actions will be performed.
- Report failures honestly.

## Success criteria
- The agent completes the scenario end to end.
- All expected files exist.
- The final report matches the actual results.
- Errors are detected and reported.
- The user can review the plan before execution.

## First test cases
1. Empty project folder.
2. Existing folder with files.
3. Missing permissions.
4. File creation failure.
5. Repeated request.

## Current limitations
Prototype 0.1 is a local experiment, not a fully autonomous personal AI. Integrations, voice, long-term memory, and advanced local/cloud routing will be developed later.

## Core principle
Orbisent does not merely explain how to achieve a goal. It plans, acts, verifies, and reports.
