# OpenSKU Progress Logs

This directory stores execution logs for project milestones and real validation runs.

The logs are part of the product evidence. A milestone is not complete unless its log exists and includes what was done, why it was done, how it was verified, and what remains uncertain.

## Required Log Template

```markdown
# <YYYY-MM-DD> - <Milestone Or Run Name>

## Context

- Branch:
- Commit:
- Goal:
- Scope:

## Thinking

Why this milestone matters.
What tradeoff was chosen.
What alternatives were rejected and why.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|

## Evidence

Links to files, run ids, screenshots, reports, command outputs.

## Validation

What was tested.
What passed.
What failed.
What was not tested and why.

## Decision

Proceed / retry / block / change scope.

## Next

Exact next steps.
```

## Run Log Location

Real live agent runs should store evidence under:

```text
docs/progress/runs/<YYYY-MM-DD>/<case_id>/
├── run-log.md
├── final-response.md
├── validator-output.txt
├── artifacts-manifest.json
├── screenshots/
└── notes.md
```

## Quality Rule

Do not write vague logs. A good log names the command, the file, the result, and the decision it caused.

