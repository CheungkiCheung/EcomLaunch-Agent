# OpenSKU Launch Team Manual MVP

This folder contains the current manual test materials for the OpenSKU-based
OpenSKU Launch Team agent.

The runtime path is:

```text
OpenSKU Launch Team chat
-> Flash by default
-> task delegation remains enabled; todo-plan tracking is disabled
-> ecom-launch skill
-> the smallest useful set of three active custom specialists
-> public web evidence and/or uploaded material
-> direct answer or files under /mnt/user-data/outputs
```

OpenSKU Launch Team does not call every specialist for every question. It answers short
questions directly and delegates only when research, offer design, asset
creation is independently useful. The frontend caps useful
parallel delegation at two specialists.

An explicitly requested complete Pack uses all three active roles in sequence,
keeps the seven candidate files compact, writes them in at most two lead-model
turns, then runs deterministic delivery preflight. Each configured output write
returns current-request Pack completeness. After assembly starts, RunBudget
keeps only write/replace tools until 7/7, then permits only `present_files`.
The retained Evidence Checker
definition is currently disabled for OpenSKU Launch Team.

## Files

- `demo-brief.portable-coffee-tumbler.json`: example launch brief.
- `demo-run-2026-06-09.md`: historical smoke-run notes; it may describe an
  earlier runtime and is not the current product contract.
- `manual-run-prompt.md`: prompt for an explicit complete Launch Validation Pack.
- `subagents.ecom-launch.yaml`: four retained specialist definitions; OpenSKU Launch Team currently enables the first three.
- `USER_MANUAL.md`: current user-facing guide for OpenSKU Launch Team and Growth Analyst.

## Current specialists

- `market-voc-researcher`
- `offer-architect`
- `asset-studio`

`evidence-checker` remains defined for later reactivation but is not an active
OpenSKU Launch Team specialist or delivery requirement.

Growth Analyst is an independent top-level agent with compatibility ID
`data-inspector`; it is not an OpenSKU Launch Team specialist.

## Local setup

1. Copy `config.example.yaml` to `config.yaml` if needed.
2. Ensure the retained specialist definitions from `subagents.ecom-launch.yaml`
   exist under `subagents.custom_agents` in `config.yaml`.
3. Ensure `skills/custom/ecom-launch/SKILL.md` and
   `skills/custom/pm-skills/` exist.
4. Install local Chromium once if the configured `web_fetch` provider needs it:
   `cd backend && uv run playwright install chromium`.
5. Start or restart the application when infrastructure configuration changed.
6. Open `/workspace/agents/ecom-launch/chats/new`.
7. Ask a short question, or paste `manual-run-prompt.md` for a complete-pack run.

New OpenSKU Launch Team chats default to Flash. The route adds `is_plan_mode=false`,
`subagent_enabled=true`, and `max_concurrent_subagents=2` to the run context.
This keeps specialists available without spending extra model turns on todo-plan
creation and updates.

`agents/ecom-launch/config.yaml` also applies a per-request run budget: at most
20 lead-model responses may continue into tool work, at most three subagent runs
may start, only the three active specialist types may start, each specialist type runs once, observed lead + subagent usage is
bounded at 500,000 tokens, and remaining wall time clamps specialist timeouts.
Each specialist also receives a smaller model-call/token finalization budget so
it returns partial structured findings before LangGraph recursion exhaustion.
After `present_files` succeeds, the run budget injects a terminal-delivery
instruction and rejects any new tool calls, so a completed Pack cannot silently
start another research phase.

When `present_files` preflight fails, the lead receives exact issues and only
`write_file`/`str_replace` remain available. A successful targeted revision
returns the run to presentation-only mode, preventing another manual readback.

For the exact seven-file Pack, `present_files` enforces a deterministic
preflight. Delivery remains blocked until required files exist, JSON/CSV is
parseable, every `observed_public` entry and competitor row has an HTTP(S) URL,
and no-sample consumer copy is free of obvious first-person experience and
unconfirmed promotional feature claims. Any remaining issue is returned with an
exact file and line and must be fixed before the files can appear in the UI.
This preflight checks URL syntax, not whether the linked page independently
supports the claim, so every complete Pack is labeled `未经过独立 Evidence Checker 审计`.

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
- every `observed_public` ledger entry includes a direct source URL
- the competitor table includes a source URL per directly observed row
- no-sample consumer copy contains no fabricated usage, testimonial, or test outcome
- the final delivery states `未经过独立 Evidence Checker 审计`
- the final delivery does not claim independent source-to-claim verification
- the final delivery is declarative and does not ask another decision question
- a complete run stops after presenting the requested Pack
- failed or timed-out research lowers confidence instead of being replaced by unsupported claims
- the final answer distinguishes evidence, estimates, assumptions, and unknowns
- private merchant metrics and unverified product claims are not invented
- any generated JSON or CSV artifact is parseable
- complete-pack files are written under `/mnt/user-data/outputs` and presented

The default local `web_fetch` provider may use HTTP fetching and local browser
rendering for public pages. It must not bypass login walls, CAPTCHA, anti-bot
systems, or private ecommerce dashboards.
