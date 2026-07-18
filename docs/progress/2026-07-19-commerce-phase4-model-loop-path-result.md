# Commerce Case Agent Phase 4 — Model Router, Goal Loop, and Path Result

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic orchestration control contracts complete
> Model requests: `0`

## Outcome

Phase 4 now has a deterministic control plane around future Lead, Path and Verification model calls. This milestone does not execute a model and does not claim that Agent behavior has passed.

Implemented under `backend/app/commerce/agents/`:

- rules-first `ModelRouter` with logical profile binding, effort, upgrade reasons and remaining-token caps;
- fail-closed capability handling when a requested binding cannot support vision or tool use;
- atomic model-escalation budget consumption;
- `model.assigned` Domain Event contract;
- normalized `PathResult` with structured observations, traceable Evidence, Hypothesis relations, Unknowns, next paths, tool hashes, cost and provider execution trace;
- `GoalLoopController` with explicit Continue/Stop decisions and the frozen stop-reason taxonomy;
- consecutive no-new-evidence tracking that resets only for a genuinely new Evidence ID;
- safe Checkpoint contract containing references, hashes, budgets, active tasks, assignments, skill versions and tool-state digests;
- `budget.exceeded`, `goal_loop.continued` and `goal_loop.stopped` Domain Event contracts.

The reusable `deerflow.*` Harness was not modified and still has no dependency on `app.*`.

## Model routing boundary

`DynamicPathRouter` and `ModelRouter` remain separate:

```text
DynamicPathRouter: Capability + anomaly signal → which 0–3 evidence paths run
ModelRouter: fixed Agent role + risk/complexity/budget → logical model assignment
```

The current logical profiles all bind to the configured alias `deepseek-reasoner`, but an alias is not accepted as proof of the served model identity. Future execution adapters must still run the fresh DeepSeek V4 preflight and record the actual `deepseek-v4...` identity for every Agent behavior test.

An upgrade from the base profile consumes `model_escalations` before the assignment is returned. Exhausted escalation or token budget raises `BudgetExceededError`; unsupported vision raises `ModelCapabilityError`. There is no model fallback.

## Path Result evidence boundary

`PathResult` cannot be a Markdown-only narrative. It must carry:

- structured `PathObservation` records;
- `PathEvidenceItem` records linked to Fact or MetricObservation IDs;
- exact unions of supported and contradicted Hypothesis IDs;
- explicit `PathUnknown` records when evidence is unavailable;
- tool request/response SHA-256 values rather than raw payload copies;
- input/output Token, latency, request ID, actual model identity, retry, stop reason and version metadata.

The contract rejects:

- untraceable Evidence;
- a Hypothesis marked both supported and contradicted;
- supported/contradicted IDs that do not exactly match Evidence relations;
- tool-call count mismatches;
- raw tool-response fields.

## Goal Loop and Checkpoint semantics

One call to `GoalLoopController.advance` records one completed assessment iteration, updates Evidence/Hypothesis references and returns one explicit decision.

Stop reasons covered:

- `goal_achieved`;
- `goal_partially_achieved`;
- `awaiting_user_input`;
- `awaiting_approval`;
- `capability_blocked`;
- `budget_exceeded`;
- `no_new_evidence`;
- `policy_blocked`;
- `tool_failure`;
- `cancelled`.

Policy denial, terminal tool failure and exhausted budget do not retry. Capability loss preserves a partial result when one exists. The no-progress threshold stops at the configured consecutive count and resets to zero after a new Evidence ID.

Checkpoint fields are closed and versioned. Attempts to inject fields such as `api_key` or `chain_of_thought` fail Pydantic validation. Tool state contains only names, status, hashes and error codes, not raw credentials or payloads.

This milestone provides the Checkpoint contract only. Durable persistence, resume-token verification and process-restart restoration remain Task 4.10.

## TDD evidence

RED was observed before implementation:

```text
ModelRouter: ModuleNotFoundError: app.commerce.agents.model_router
PathResult: ModuleNotFoundError: app.commerce.agents.path_result
Budget streak: AttributeError: BudgetManager.record_iteration
Goal Loop: ModuleNotFoundError: app.commerce.agents.goal_loop
```

After the minimum implementations were added, the targeted tests passed.

## Validation

Targeted Agent control tests:

```text
tests/commerce/agents/test_model_router.py: 4 passed
tests/commerce/agents/test_path_result.py: 5 passed
tests/commerce/agents/test_budget.py + test_goal_loop.py: 14 passed
```

Full deterministic Commerce regression:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce \
  --ignore=tests/commerce/evaluation/test_real_model_preflight_live.py \
  --ignore=tests/commerce/data/test_semantic_candidate_service_live.py \
  tests/test_commerce_feature_flag.py

202 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static and diff checks:

```text
.venv/bin/ruff check app/commerce app/gateway/app.py tests/commerce \
  tests/test_commerce_feature_flag.py

All checks passed!

git diff --check
exit code: 0
```

## Not validated by this milestone

- no Lead Agent call was made;
- no Path Agent call was made;
- no Tool Selection behavior was evaluated;
- no structured-output repair call was made;
- no Verification model call was made;
- no Gold Case Agent E2E was run;
- no durable Checkpoint persistence/resume was run;
- no new DeepSeek request was needed because all implemented behavior is deterministic control logic.

These items remain blocked from being called PASS until they make fresh, identity-verified DeepSeek V4 requests. Existing Semantic Candidate live evidence remains valid only for that already-tested model path.

## Next

Implement Investigation Run persistence and start/read APIs so a real Case can create a durable Run, append orchestration events and restore the safe Checkpoint contract before connecting the first live `FulfillmentPathAgent`.
