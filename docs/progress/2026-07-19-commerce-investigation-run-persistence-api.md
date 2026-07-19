# Commerce Case Agent — Investigation Run Persistence and API

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic Run persistence and HTTP slice complete
> Model requests: `0`

## Outcome

Commerce Case Agent can now turn an existing Case into a bounded, auditable Investigation Run without pretending that an Agent has already executed.

Implemented:

- `CommerceRun` aggregate with queued/running/waiting/completed/failed/timeout/cancelled/blocked states;
- validated Run timestamps, wait reason, terminal stop reason and optimistic version;
- `commerce_runs` projection table and independent migration;
- append-only `commerce_run_checkpoints` table storing strict `GoalLoopCheckpoint` JSON;
- Workspace/Case-scoped Run Repository, idempotency hash lookup and optimistic save;
- Checkpoint sequence allocation, latest/list reads and Case/Goal membership checks;
- atomic Run + `run.created` Domain Event mutation;
- atomic Checkpoint + `run.checkpoint_saved` Domain Event mutation;
- Run stream invariant requiring `run.created` at sequence 1;
- idempotent Investigation Start and Run/Checkpoint/Event read APIs.

## Honest execution state

The start endpoint creates:

```text
status: queued
phase: planning
started_at: null
latest_checkpoint: null
```

There is no Worker acquisition or Agent call in this milestone. Therefore the API never returns `running` merely because the user clicked Start. A future Worker must explicitly transition the Run and append the corresponding Domain Event.

## API contracts

```text
POST /api/commerce/cases/{case_id}/investigations
GET  /api/commerce/cases/{case_id}/runs
GET  /api/commerce/runs/{run_id}
GET  /api/commerce/runs/{run_id}/events
GET  /api/commerce/runs/{run_id}/checkpoints
```

The start request requires a client idempotency key. Only its SHA-256 is persisted. Repeating the same Workspace + Case + key + Goal returns the existing Run with `created: false`; reusing the key for a different Goal returns HTTP 409. Concurrent requests are also resolved through the same database uniqueness boundary.

All Run, Checkpoint and Event reads are Workspace-scoped. A Run in another Workspace returns 404 rather than leaking its existence.

## Persistence and event invariants

Run and Checkpoint writes use `SqlCommerceUnitOfWork`:

```text
Create Run row + append run.created → one SQL transaction
Append Checkpoint row + append run.checkpoint_saved → one SQL transaction
```

If Checkpoint Case/Goal membership validation fails, neither the Checkpoint nor the Event is committed.

Case and Run sequences remain independent. Eight concurrent Run creations for one Case produced:

```text
each Run stream: run_sequence = 1
Case stream: case_sequence = 1..9 without gaps
```

The first event in every Run stream must be `run.created`; a `run.progressed` first event is rejected.

## TDD evidence

RED was observed before implementation:

```text
Run domain: ImportError: RunStatus
Run persistence: ModuleNotFoundError: app.commerce.persistence.runs
ORM: ImportError: RunCheckpointRow
Run API: ImportError: get_commerce_run_service
```

The minimum domain, persistence and HTTP implementations were then added until the tests passed.

## Validation

Targeted validation covered:

- Run lifecycle and invalid transitions;
- Workspace-scoped Run round trip and optimistic concurrency;
- idempotency uniqueness and rollback;
- append-only Checkpoint order/latest reads;
- Checkpoint/Event atomic failure path;
- Case and Run event sequence invariants;
- SQLite migration and PostgreSQL DDL compilation;
- Investigation Start retry/conflict behavior;
- Run Detail, Case Run List, Checkpoint and Event endpoints;
- Workspace and missing-entity boundaries;
- Commerce feature-flag route mounting.

Full deterministic Commerce regression:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce \
  --ignore=tests/commerce/evaluation/test_real_model_preflight_live.py \
  --ignore=tests/commerce/data/test_semantic_candidate_service_live.py \
  tests/test_commerce_feature_flag.py

213 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static and diff validation:

```text
.venv/bin/ruff check app/commerce app/gateway/app.py tests/commerce \
  tests/test_commerce_feature_flag.py

All checks passed!

git diff --check
exit code: 0
```

## Not validated by this milestone

- no queue Worker acquired a Run;
- no Run transitioned to `running` through an executor;
- no Agent or model request was made;
- no Path Tool Selection or Structured Output behavior was evaluated;
- no process-restart resume or resume-token verification was executed;
- no live PostgreSQL instance was used.

These remain separate tasks. Any future Agent behavior validation must make fresh, identity-verified DeepSeek V4 requests and stop rather than fall back when that model is unavailable.

## Next

Implement a deterministic Run acquisition/execution shell that restores the latest Checkpoint, builds the initial ContextPacket and persists every state transition before connecting the first real `FulfillmentPathAgent` call.
