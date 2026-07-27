# Commerce Case Agent - DeerFlow Subagent Adapter Contract

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic adapter/Fulfillment wrapper verified; live gate blocked
> Model requests: one fresh DeepSeek V4 preflight attempt; provider unavailable

## Outcome

Commerce now has a strict application adapter boundary for bounded DeerFlow
subagent execution. The adapter owns no Case, Evidence, Repository, or Unit of
Work and does not become a second business state machine.

```text
CommerceAgentTask
→ minimal PathContextPacket prompt
→ bounded DeerFlow SubagentConfig/Executor
→ explicit Harness lifecycle projection
→ fail-closed PathResult validation
→ CommerceSubagentOutcome
→ fenced CommerceSubagentCommitter
→ atomic Evidence/Event/Checkpoint transaction
```

`CommerceAgentTask` carries only typed references and version bindings:
workspace, Case, Run, Path, context hash, budget, model assignment, skill
version, Tool allowlist, lease worker ID, fencing token, trace and correlation IDs. Lease
credentials and raw prompts/responses are not persisted by this adapter.

## Boundary Rules

- The recursive `task` Tool is always denied.
- Only the Path task allowlist is passed to the DeerFlow executor.
- Parent Skills are not inherited; the Commerce task carries the explicit Skill
  identity and version until the dedicated Commerce Skill loader is migrated.
- Context workspace, Case, Path, Budget, Tool allowlist and output schema must
  match the task before execution.
- Completed output must be strict JSON and a valid `PathResult`.
- Path type, context hash, model assignment, Skill version, schema version and
  Tool traces are checked against the task.
- Provider request IDs, actual model identity, Token usage, Latency, Retry and
  Stop Reason are protected runtime fields. The Fulfillment normalizer sources
  them from DeerFlow `AIMessage`, token collector and runtime timestamps instead
  of accepting model-authored values.
- DeerFlow Harness contains no import of `app.commerce.*`; a Python AST boundary
  test enforces that dependency direction.
- The Harness emits only secret-free structured Tool traces: call ID, Tool name,
  request/response hashes, status and runtime latency. Commerce validates the
  allowlist and writes `tool.completed` / `tool.failed` events without parsing
  Tool response prose.
- `CommerceSubagentCommitter` revalidates result hash and version bindings,
  rejects stale lease/fencing credentials, rebases parallel Path Evidence on
  the latest Case version, and atomically writes a Path Evidence batch,
  terminal Path/Tool events and the post-call Checkpoint.

The adapter bootstraps DeerFlow's existing Agent initialization order lazily so
importing Commerce does not trigger the Harness package cycle. The Commerce
application remains the only side that may depend on the Harness.

## Verification

```text
Adapter + package boundary: 34 passed
Adapter + Context contracts + package boundary: 36 passed
Fulfillment Subagent normalization contracts: 6 passed
Full deterministic Commerce suite: 296 passed, 9 live tests deselected
DeerFlow SubagentExecutor regression: 50 passed
Relevant Harness/model/middleware regression: 108 passed
Ruff: passed
git diff --check: passed
LangChain pending-deprecation warning: 1 unrelated warning
```

The Fulfillment Subagent live gate was attempted with a fresh request and was
blocked by the provider connection:

```text
status: blocked_real_model_unavailable
endpoint: https://api.deepseek.com/v1
provider: deerflow.models.patched_deepseek:PatchedChatDeepSeek
request_attempt_count: 1
retry_count: 0
actual_model_identity: null
provider_request_id: null
error_code: APIConnectionError
error_message: Connection error.
```

This is a real-model blocker, not a passing or skipped Agent test. No Mock,
Fake, Replay, cached response, alternate model, or retry escalation was used.

The tests use manually constructed `SubagentResult` values only to verify
deterministic lifecycle and boundary contracts. They are not Agent behavior
evidence and do not replace the required fresh DeepSeek V4 test.

## Remaining Gate

Gate C is complete. The next executable live step is to rerun the Fulfillment
DeerFlow Subagent after Provider recovery, then compare its persisted Evidence,
Tool/Path events and Checkpoints with the legacy Worker on the same Gold Case.
No old orchestration can be removed before that live parity gate passes.
