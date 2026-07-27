# Commerce Continuous Lead Turn Live Gate

Date: 2026-07-19

## Proven transaction

```text
persisted Observe
-> DynamicPathRouter
-> LeadLoopPlanner
-> Fulfillment + ReviewExperience bounded Subagents
-> concurrent fan-out
-> Evidence Barrier
-> persisted Scope reload
-> multi-Path Lead synthesis
-> Hypothesis + Domain Event + Checkpoint
-> fresh read-only Answer without Path rerun
```

The live gate uses the official DeepSeek endpoint, requires server-side `deepseek-v4...` identity, disables provider retries and does not accept Mock, Replay, cache or fallback results. The Router selected Fulfillment and ReviewExperience from real deterministic anomaly signals. Both selected tasks reached explicit terminal states; the Barrier required at least one completed Path and preserved unsuccessful sibling state without fabricating Evidence.

The first Lead turn writes only claims backed by Barrier-released persisted Evidence. The second turn asks a follow-up question on the same Case. It creates no Path task, appends no Hypothesis and makes a new identity-verified model request with role `answer` and profile `fast_structured`.

## Real-model telemetry

Accepted synthesis:

```text
actual model: deepseek-v4-flash
role/profile: lead / strong_synthesizer
tokens: 3,094
latency: about 3.69s
provider attempts: 1
provider retries: 0
```

Read-only answer:

```text
actual model: deepseek-v4-flash
role/profile: answer / fast_structured
tokens: 3,445
latency: about 3.45s
provider attempts: 1
provider retries: 0
```

One earlier fresh run returned forbidden inferential language (`indicating`). The deterministic validator rejected it. The new bounded structured-repair path then made one separate fresh V4 call rather than a provider retry:

```text
original: 2,954 tokens, about 3.63s, unique Provider ID, retry 0
repair:   3,443 tokens, about 2.81s, unique Provider ID, retry 0
```

Both attempts are persisted in `attempt_telemetry`; aggregate Token/Latency and one repeated-action unit enter the Run budget.

## State and failure semantics

- `WAIT` appends `lead.waiting` and a resumable Checkpoint, transitions the Run to `waiting`, then releases the lease.
- Resume acquisition transitions the Run back to `running`, clears the Run wait reason and increments the fencing token. The historical Checkpoint keeps the wait reason for audit.
- `CANCEL` appends `lead.stopped`, stores the terminal Run state and releases the lease; the old worker credential fails heartbeat.
- A failed or blocked Path never becomes completed and never releases fabricated Evidence.

## Verification

```text
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/agents/test_continuous_lead_turn_live.py -m real_model -vv
1 passed, exit 0

PYTHONPATH=. .venv/bin/pytest -q -m 'not real_model' tests/commerce
338 passed, 15 real-model tests deselected, exit 0
```

## Remaining boundary

- Fresh Verification must move from the legacy direct Engine to a DeerFlow Subagent built from persisted Evidence plus deterministically reconstructed metrics.
- Verification verdicts must append Hypothesis versions and drive GoalLoop stop/replan decisions in the new transaction.
- New investigation angles still need a distinct idempotent Replan Run instead of executing inside the prior Run.
