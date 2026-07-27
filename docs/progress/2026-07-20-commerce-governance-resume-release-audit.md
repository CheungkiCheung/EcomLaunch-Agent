# Commerce Governance, Resume, Fault and Release Audit

> Date: 2026-07-20  
> Branch: `feature/commerce-case-agent`  
> Status: deterministic backend governance/resume audit passed  
> Model requests in this milestone: `0`

## Outcome

This milestone closes four backend control-plane gaps without promoting the real Shadow Skill Candidate and without making any model request:

```text
Mapping confirmation
→ recompute Capability

Unknown remote Path outcome
→ fenced reconciliation
→ preserve verified partial Evidence
→ block old Run
→ explicit Replan only

Skill Candidate shadow
→ human promotion API
→ Active Pointer
→ rollback API

State/Pointer or Checkpoint/Projection crash
→ recover same durable command
→ no duplicate terminal event/state
```

The accepted four-Gold fresh DeepSeek V4 v11 gate remains the latest Agent behavior evidence. This milestone is deterministic business, persistence, security and lifecycle work, so calling a model would not add valid evidence.

## 1. Mapping Confirmation Resume

New HTTP contract:

```text
POST /api/commerce/datasets/{dataset_id}/mapping-resume
```

The request contains one or more semantic confirmations plus an idempotency key. The server derives the reviewer from `X-Commerce-Actor-Id`; the body cannot spoof reviewer identity.

Contracts:

- every table/column is validated before any confirmation is written;
- duplicate columns in one batch are rejected;
- `WorkspaceSemanticStore.confirm_many()` replaces the semantic mapping file once, so an invalid second item cannot leave the first item partially committed;
- confirmations persist `confirmed_by` and one shared confirmation timestamp;
- an immutable request receipt binds Dataset, actor, semantic choices and idempotency key;
- replay returns the persisted Mapping and Capability snapshot without changing confirmation time;
- a conflicting request under the same key returns `409`;
- the response immediately returns the recomputed `SemanticMappingProfile` and `CapabilityProfile`.

The deterministic test starts with an ambiguous required `orders.id` field. Fulfillment is initially `unavailable`; after explicit human confirmation it becomes routable as `partial` because only optional semantics remain missing.

## 2. WAIT and Approval Resume Classification

`RunResumeClassifier` now recognizes durable wait Checkpoints instead of classifying them as an unknown shape:

| Persisted state | Disposition |
| --- | --- |
| `awaiting_user_input` Checkpoint + matching `lead.waiting` | `waiting_for_user_input` |
| `awaiting_approval` Checkpoint + matching `lead.waiting` | `waiting_for_approval` |
| matching wait plus authoritative `waiting -> running`, `resumed_from_wait=true`, fencing token `>= 2` | `continue_after_wait` |

A waiting Checkpoint with active Path tasks, missing `lead.waiting`, mismatched wait reason, malformed status transition or invalid fencing token fails closed.

Action approval remains a separate structured lifecycle (`approval.requested`, `approval.approve/reject/modify`, Action status). The Investigation Run does not infer approval from chat text.

## 3. Tool Failure Resume

An Investigation Run that ended with `status=failed` and `stop_reason=tool_failure` may now become the parent of an independent Replan Run.

The failed parent is immutable. It is not transitioned back to running, and a generic unclassified failure is not eligible. Replan also rejects non-Investigation parent Run types.

This keeps retry attribution explicit:

```text
failed parent Run
→ repair deterministic Tool or configuration
→ new Replan Run ID
→ new Task/Provider telemetry
```

## 4. Unknown External Outcome Reconciliation

New HTTP contract:

```text
POST /api/commerce/runs/{run_id}/reconciliations
```

Only the explicit `abandon_unknown_outcome` decision is currently supported. It does not authorize another model request.

Execution:

1. Load authoritative Run, latest Checkpoint and Run Event stream.
2. Require `await_retry_decision` or `reconcile_partial_evidence`.
3. Refuse to steal a live lease.
4. After expiry, acquire a higher fencing token.
5. Verify every partial Evidence ID exists in the same Workspace and Case.
6. Append stable, unique `path.blocked` event(s), `run.reconciled` and a post-call Checkpoint.
7. Clear active tasks, count the unknown attempt as one loop iteration and preserve verified partial Evidence IDs.
8. End the old Run as `blocked` with `stop_reason=external_outcome_unknown`.
9. Release the reconciliation lease.
10. Require a distinct Replan Run for any later retry.

The command stores only SHA-256 idempotency/request digests. Actor and bounded reason are auditable; no provider response text or secret is persisted.

Fault injection covers a second crash after `path.blocked + run.reconciled + post-checkpoint` commit but before the Run projection changes. The retry waits for the reconciliation lease to expire, acquires a higher fencing token, completes the original Run transition and release, and does not append a second terminal Path event.

## 5. Skill Human Review, Promotion and Rollback API

New HTTP contracts:

```text
POST /api/commerce/skill-candidates/{candidate_id}/promote
GET  /api/commerce/skills/{skill_name}/active
POST /api/commerce/skills/{skill_name}/rollback
```

Contracts:

- Candidate remains Workspace-scoped;
- reviewer identity comes from `X-Commerce-Actor-Id`;
- promotion still requires Security Scan, Offline Eval, Regression, Holdout and at least two passing live Shadow Runs;
- Active Candidate requires a human reviewer;
- rollback requires a second human actor and a non-blank bounded reason;
- Active Pointer is a versioned typed contract rather than an unvalidated dictionary;
- command receipts store request hashes and response snapshots for exact replay;
- idempotency-key reuse for another subject or reason fails closed;
- rolled-back Pointer removes the Candidate as the active implementation and restores the base version;
- corrupt Pointer JSON fails closed.

Fault injection covers both state transitions:

```text
ACTIVE state appended, pointer write fails
→ retry reconstructs the matching Active Pointer

ROLLED_BACK state appended, pointer write fails
→ retry reconstructs the matching rollback Pointer
```

The retry validates status, reviewer and rollback reason before repairing the Pointer. It cannot use this recovery path to bypass gates.

The real `commerce-diagnostic-synthesis@1.3.0` Candidate was not promoted in this milestone. It remains `shadow` until an explicitly authorized human review.

## 6. Harness Security Import Boundary

Running `test_sandbox_tools_security.py` alone exposed an eager-import cycle:

```text
deerflow.sandbox.tools
→ deerflow.agents.__init__ / deerflow.tools.__init__
→ agent factory / builtin tools
→ deerflow.sandbox.tools
```

`deerflow.agents` and `deerflow.tools` now preserve their public exports through lazy `__getattr__` loading. Low-level sandbox and Tool type modules can be imported independently, while requesting `create_deerflow_agent` or `make_lead_agent` still primes the enabled-Skill cache.

This is a Harness fix and contains no Commerce import.

## 7. Verification Evidence

### Full deterministic Commerce gate

```text
PYTHONPATH=. .venv/bin/pytest -q -m 'not real_model' tests/commerce

427 passed, 23 real-model tests deselected
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

### Security, permission, lifecycle, failure and fault gate

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_sandbox_tools_security.py \
  tests/test_security_scanner.py \
  tests/test_skill_permissions.py \
  tests/test_subagent_prompt_security.py \
  tests/test_model_lifecycle.py \
  tests/test_subagent_executor.py \
  tests/commerce/persistence/test_run_leases.py \
  tests/commerce/actions/test_action_execution.py \
  tests/commerce/actions/test_internal_connectors.py \
  tests/commerce/agents/test_subagent_fanout.py \
  tests/commerce/agents/test_subagent_supervisor.py \
  tests/commerce/api/test_run_reconciliation.py \
  tests/commerce/api/test_skill_candidate_router.py

215 passed
exit code: 0
```

### Harness lazy-import and sandbox regression

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_sandbox_tools_security.py \
  tests/test_create_deerflow_agent.py \
  tests/test_thread_state_reducers.py \
  tests/test_gateway_services.py \
  -m 'not real_model'

204 passed
exit code: 0
```

### Performance-focused deterministic gate

```text
31 passed in 1.58s
```

Measured slowest relevant calls on this local machine:

| Contract | Duration |
| --- | ---: |
| two-Path parallel fan-out and join | `0.12s` |
| unknown outcome HTTP reconciliation + replay/conflict | `0.10s` |
| concurrent lease acquisition single-winner test | `0.09s` |
| Action monitor execution + rollback | `0.07s` |
| reconciliation crash recovery | `0.06s` |
| mapping confirmation resume | `0.03s` |

The fan-out test also asserts elapsed wall time stays below `0.18s` for simulated `0.08s` and `0.12s` paths, proving concurrency rather than serial `0.20s` execution. These are deterministic control-plane timings, not production provider latency benchmarks.

### Static checks

```text
Ruff Commerce and touched Harness: passed
git diff --check: passed
```

### Secret boundary

- no `.env` file is tracked by Git;
- a filename-only scan found no credential-shaped `sk-...` token outside ignored environment/runtime artifact paths;
- no Key value was printed or copied into this report.

## 8. PostgreSQL Status

PostgreSQL DDL compilation and SQLite migrations are covered by deterministic tests. Live PostgreSQL is not accepted:

```text
127.0.0.1:5432 - no response
Docker daemon: unavailable
asyncpg=False
psycopg=False
```

This milestone does not convert SQLAlchemy PostgreSQL compilation into a live integration claim.

## 9. Known Limits

- The real Shadow Skill Candidate remains unreviewed and unpromoted.
- Mapping and Skill governance receipts are local file-backed development storage; production multi-node deployment should move them to transactional database/object storage with compare-and-swap semantics.
- No external merchant write Connector is enabled.
- Workspace identity still comes from explicit headers rather than production membership authorization.
- Live PostgreSQL is blocked by local service/runtime dependencies.
- Frontend, War Room, browser QA, responsive/accessibility checks and full-stack performance are not part of this backend audit.
- No fresh DeepSeek V4 request was made because all changed behavior is deterministic control-plane logic. The latest Agent evidence remains the four-Gold v11 report.

## Next

Move to final architecture/demo/interview evidence while keeping the real Candidate in Shadow. The next user decision is required when selecting each generated frontend visual before React implementation, or before any actual Skill promotion/external deployment action.
