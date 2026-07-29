# EcomLaunch Manual MVP

This folder contains the current manual test materials for the DeerFlow-based
EcomLaunch agent.

The runtime path is:

```text
EcomLaunch chat
-> Flash by default
-> task delegation remains enabled; todo-plan tracking is disabled
-> ecom-launch skill
-> the smallest useful set of four custom specialists
-> public web evidence and/or uploaded material
-> direct answer or files under /mnt/user-data/outputs
```

EcomLaunch does not call every specialist for every question. It answers short
questions directly and delegates only when research, offer design, asset
creation, or evidence review is independently useful. The frontend caps useful
parallel delegation at two specialists.

## Files

- `demo-brief.portable-coffee-tumbler.json`: example launch brief.
- `demo-run-2026-06-09.md`: historical smoke-run notes; it may describe an
  earlier runtime and is not the current product contract.
- `manual-run-prompt.md`: prompt for an explicit complete Launch Validation Pack.
- `subagents.ecom-launch.yaml`: current four-specialist `subagents:` config.
- `USER_MANUAL.md`: current user-facing guide for EcomLaunch and Growth Analyst.

## Current specialists

- `market-voc-researcher`
- `offer-architect`
- `asset-studio`
- `evidence-checker`

Growth Analyst is an independent top-level agent with compatibility ID
`data-inspector`; it is not an EcomLaunch specialist.

## Local setup

1. Copy `config.example.yaml` to `config.yaml` if needed.
2. Ensure the four specialist definitions from `subagents.ecom-launch.yaml`
   exist under `subagents.custom_agents` in `config.yaml`.
3. Ensure `skills/custom/ecom-launch/SKILL.md` and
   `skills/custom/pm-skills/` exist.
4. Install local Chromium once if the configured `web_fetch` provider needs it:
   `cd backend && uv run playwright install chromium`.
5. Start or restart the application when infrastructure configuration changed.
6. Open `/workspace/agents/ecom-launch/chats/new`.
7. Ask a short question, or paste `manual-run-prompt.md` for a complete-pack run.

New EcomLaunch chats default to Flash. The route adds `is_plan_mode=false`,
`subagent_enabled=true`, and `max_concurrent_subagents=2` to the run context.
This keeps specialists available without spending extra model turns on todo-plan
creation and updates.

`agents/ecom-launch/config.yaml` also applies a per-request run budget: at most
16 lead-model responses may continue into tool work, at most four subagent runs
may start, each specialist type runs once, observed lead + subagent usage is
bounded at 500,000 tokens, and remaining wall time clamps specialist timeouts.
Each specialist also receives a smaller model-call/token finalization budget so
it returns partial structured findings before LangGraph recursion exhaustion.

## Complete-pack artifacts

An explicitly requested complete Launch Validation Pack may create:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

Ordinary requests should return only the answer or artifacts that are useful for
that request.

## Acceptance criteria

- the agent reads and follows the `ecom-launch` skill
- short questions do not start all specialists
- specialist names and tool boundaries match `subagents.ecom-launch.yaml`
- no more than two independent specialists run concurrently
- no specialist type runs twice in one user request
- a complete run stops after presenting the requested Pack
- failed or timed-out research lowers confidence instead of being replaced by unsupported claims
- the final answer distinguishes evidence, estimates, assumptions, and unknowns
- private merchant metrics and unverified product claims are not invented
- any generated JSON or CSV artifact is parseable
- complete-pack files are written under `/mnt/user-data/outputs` and presented

The default local `web_fetch` provider may use HTTP fetching and local browser
rendering for public pages. It must not bypass login walls, CAPTCHA, anti-bot
systems, or private ecommerce dashboards.
