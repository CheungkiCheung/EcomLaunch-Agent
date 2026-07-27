# Commerce Fulfillment Subagent Live Gate

Date: 2026-07-19

## Scope

The first Commerce Path was migrated through the DeerFlow Subagent Harness while retaining the legacy `FulfillmentPathAgent` as the behavior baseline. The migration was tested against `GC-FULFILLMENT-001` and the official DeepSeek endpoint configured by `DEEPSEEK_API_KEY` in the ignored local `.env`.

The new path is now exercised as:

```text
PathContextPacket
-> CommerceAgentTask
-> DeerFlow SubagentExecutor
-> CommerceSubagentAdapter / strict normalizer
-> CommerceSubagentOutcome
-> Supervisor heartbeat/poll
-> fenced Committer
-> Evidence + Domain Events + Checkpoints
```

## Fresh-model evidence

Every live test makes a new `real_model_preflight` request before the Agent request. The preflight requires the provider response to expose an explicit `deepseek-v4...` identity and records provider request/response IDs, token usage, latency, retry count, stop reason, and version metadata without storing Prompt or response text.

The current provider returned `deepseek-v4-flash`. The live requests used one provider attempt and zero provider retries. The tests fail closed on missing credentials, quota, service errors, unverifiable identity, missing telemetry, invalid structured output, or persistence contract violations.

## Commands and results

Deterministic Commerce and Harness checks run with the repository `.venv` because the sandbox cannot read the user-level `uv` cache:

```text
PYTHONPATH=. .venv/bin/pytest -q -m 'not real_model' tests/commerce
338 passed, 15 real-model tests deselected.

PYTHONPATH=. .venv/bin/pytest -q tests/test_model_factory.py
44 passed

PYTHONPATH=. .venv/bin/pytest -q tests/test_subagent_executor.py
52 passed

PYTHONPATH=. .venv/bin/pytest -q tests/commerce/agents/test_fulfillment_subagent.py tests/commerce/agents/test_subagent_adapter.py tests/commerce/agents/test_subagent_committer.py tests/commerce/agents/test_subagent_supervisor.py
50 passed
```

Fresh DeepSeek V4 gates:

```text
tests/commerce/agents/test_fulfillment_subagent_live.py
1 passed

tests/commerce/agents/test_fulfillment_subagent_parity_live.py
1 passed

tests/commerce/agents/test_fulfillment_subagent_supervisor_live.py
1 passed
```

The parity gate compares evidence coverage for `late_delivery_rate`, `handling_time_hours`, and `transit_time_hours`, preserves explicit unknowns, keeps the same Path model assignment and Context hash, and rejects forbidden causal claims. It does not require model prose to be byte-for-byte identical.

The Supervisor gate verifies that the real Outcome's trace, provider identity, request ID, token count, latency, and tool count are carried into `path.completed`; the same outcome drives the post-call Budget snapshot. Evidence is appended atomically under the active fencing token, and pre/post Checkpoints are persisted with no active task left at terminal commit.

## Fixes found by RED tests

- `create_chat_model` now merges explicit runtime constraints into one settings dictionary, so a bounded Subagent can override configured `max_tokens`/`max_retries` without Python duplicate-keyword failure.
- `SubagentConfig.max_turns` is translated to `2 * max_turns + 1` LangGraph graph steps, reserving model/tool supersteps and a terminal publication step without changing the business turn budget.
- Fulfillment normalization binds `PathResult.trace_id` to the Commerce `AgentTask` trace before persistence.
- The Adapter accepts only schema-valid JSON extracted by the versioned Fulfillment parser when a provider returns legal fenced JSON; arbitrary prose remains blocked.
- Supervisor post-checkpoints are built from the terminal Outcome instead of being passed as stale precomputed state.

## Remaining boundary

This milestone does not claim the complete Commerce product. SellerPeer and ReviewExperience now have versioned Subagent specs and standalone fresh V4 gates; 0-3 concurrent fan-out, Evidence Barrier, shared Checkpoint accounting and a Case-level Coordinator are integrated into the fresh V4 continuous Lead transaction. Fresh Verification Subagent, Replan Runs and downstream Action/Follow-up remain pending. The legacy Worker remains intentionally preserved until those migrations and their failure/restart gates are complete.
