# Commerce Case Agent — Fenced Worker Real Path Step

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: first durable real-model Worker step verified
> Model requests: `2` (`1` fresh preflight + `1` fresh FulfillmentPathAgent)
> Successful tokens: `4,435` total (`3,950` input, `485` output)

## Outcome

The first Commerce Worker step now connects execution ownership, real Agent behavior and durable business state.

The accepted sequence is:

```text
queued Investigation Run
→ acquire Worker lease and fencing token
→ Run running
→ phase investigating
→ verified initial LeadContextPacket
→ prepare Fulfillment PathContext + ModelAssignment
→ atomic model.assigned + path.started + pre-call Checkpoint
→ lease heartbeat
→ fresh DeepSeek V4 preflight
→ fresh DeepSeek V4 FulfillmentPathAgent request
→ lease heartbeat / stale-worker check
→ actual Budget consumption
→ lease-guarded Evidence append into Case and Run streams
→ atomic path.completed + post-call Checkpoint
```

The Run remains honestly `running / investigating` after this bounded step. It is not marked completed because the remaining Paths, Lead synthesis and Verification do not exist yet.

## Fencing and Atomicity

New deterministic contracts cover:

- an active Run may advance phase without fabricating a same-status transition;
- phase cannot move backward;
- `model.assigned`, `path.started` and the pre-call Checkpoint share one transaction;
- a running Agent Evidence write with `run_id` requires the current lease;
- the Evidence event joins both authoritative Case and Run streams;
- old Worker Checkpoint and Evidence writes are rejected after fencing takeover;
- `path.completed` and the post-call Checkpoint share one transaction;
- raw lease tokens never enter Checkpoints or Domain Events.

The Worker heartbeats immediately before and after the external model call. If the lease expires or another Worker takes over, the post-call heartbeat or subsequent fenced writes fail instead of letting stale output mutate the Case.

## Checkpoints

Pre-call Checkpoint:

- iteration `0`;
- one deterministic active Path task ID;
- the exact ModelAssignment;
- active fulfillment Skill version;
- Path Context SHA-256;
- zero budget usage.

Post-call Checkpoint:

- iteration `1`;
- no active Path task;
- existing deterministic Case Evidence plus newly persisted Path Evidence IDs;
- actual provider token usage;
- actual model latency as wall-time usage;
- one consumed Path Agent;
- the same ModelAssignment, Skill and Context hash.

## Fresh Real-model Evidence

Preflight:

```text
run_id: preflight-261f8aaccd6c4e00b93f12a7c1728427
actual_model_identity: deepseek-v4-flash
provider_request_id: b44004b8-073b-4dfa-9707-1a5b01778fd0
tokens: 63 input / 11 output / 74 total
latency: ~833 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
```

Fulfillment Path:

```text
run_id: fulfillment-path-5b8050f31e844ae8b1405d9b4399c6dd
actual_model_identity: deepseek-v4-flash
provider_request_id: a8902753-0106-46a6-8c2c-c3dee60ff212
tokens: 3887 input / 474 output / 4361 total
latency: ~4200 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
model profile: balanced_tool_user
effort: medium
router output ceiling: 4000
invocation output ceiling: 1600
```

The Agent again passed the behavior gate for handling not worsening, transit worsening, traceable MetricObservation IDs and forbidden-claim absence.

## Verification

Deterministic focused tests:

```text
9 passed
exit code: 0
```

Fresh Worker live test:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_worker_fulfillment_step_live.py

1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full deterministic Commerce regression, explicitly excluding four live tests:

```text
229 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

## Known Limits

- The Worker currently supports only the initial no-Checkpoint path; resume remains fail-closed.
- A crash after some Evidence rows but before the post-call Checkpoint still requires an idempotent resume/reconciliation design.
- The lease is heartbeated around, not continuously during, the model call; the five-minute TTL currently bounds this first request.
- The Run remains active after the bounded step; a complete multi-Path/Lead/Verification loop must eventually own terminal status.
- Model-selected Tool use and structured-output repair remain unimplemented.
- Harness `run_agent` / StreamBridge adaptation is still not connected; Commerce Domain Run/Event state remains authoritative.

## Next

Add deterministic resume/reconciliation for the two safe checkpoints before expanding to the next Path Agent. The next Worker must be able to distinguish:

1. no Checkpoint: prepare and run the Path;
2. pre-call Checkpoint only: decide whether the external call can be safely retried and record duplicate-risk telemetry;
3. post-call Checkpoint: do not repeat the Path; continue to the next Goal Loop phase;
4. partial Evidence without post-call Checkpoint: reconcile idempotent Evidence IDs before continuing.
