# EcomLaunch Artifact-First MVP

This folder contains the manual MVP materials for EcomLaunch Agent.

The goal is to prove the core DeerFlow-based workflow before building a dedicated conversational EcomLaunch entry:

```text
existing DeerFlow chat
-> Ultra mode
-> ecom-launch skill
-> ask_clarification when the launch brief is too incomplete
-> ecommerce custom subagents
-> public web search/fetch
-> files under /mnt/user-data/outputs
-> present_files artifacts
```

## Files

- `demo-brief.portable-coffee-tumbler.json`: recommended demo input.
- `demo-run-2026-06-09.md`: first local smoke-run record and validation notes.
- `manual-run-prompt.md`: prompt to paste into an Ultra-mode DeerFlow chat.
- `subagents.ecom-launch.yaml`: copyable `subagents:` config block for local `config.yaml`.

## Local Setup

1. Copy `config.example.yaml` to `config.yaml` if you have not already.
2. Copy the contents of `subagents.ecom-launch.yaml` into `config.yaml`.
3. Ensure `skills/custom/ecom-launch/SKILL.md` exists.
4. Restart the backend if it is already running.
5. Start a new chat in Ultra mode so `subagent_enabled=true`.
6. Paste `manual-run-prompt.md`.

## Expected Artifacts

The run should create and present:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

Optional but useful:

```text
review-insights.json
risk-notes.md
source-list.md
```

## Acceptance Criteria

The artifact-first MVP is successful when:

- the agent reads or follows the `ecom-launch` skill
- Ultra mode exposes the ecommerce subagents through the `task` tool
- the final deliverables are saved under `/mnt/user-data/outputs`
- `present_files` is called
- `evidence-ledger.json` distinguishes observed public evidence from estimates
- no private merchant metrics are invented

## Notes

Use public data only. Do not bypass login walls, CAPTCHA, anti-bot systems, or private ecommerce dashboards.

If a source cannot provide a private metric such as GMV, CTR, CVR, ROI, ad spend, refund rate, or repeat purchase rate, mark the metric as unavailable and propose a launch test to collect it.
