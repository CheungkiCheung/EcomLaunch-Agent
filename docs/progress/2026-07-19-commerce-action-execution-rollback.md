# Commerce Action Execution and Rollback

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: internal execution, artifacts, failure semantics and rollback complete

## Outcome

Approved or auto-executable internal Actions now run through their own fenced Commerce Run:

```text
Policy-checked Action
→ idempotent EXECUTE / ROLLBACK Run
→ acquire lease + fencing token
→ internal Connector
→ real persisted Artifact
→ read-back verification
→ Action / Case / Run transition
→ release lease
```

Supported internal catalog operations:

- `no_op` immutable receipt;
- `export_audit_cohort` with content hash and physical archive rollback;
- `create_internal_task` with cancellation rollback;
- `create_metric_monitor` with disable rollback;
- `request_missing_data` with cancellation rollback.

Execution and rollback endpoints:

```text
POST /api/commerce/actions/{action_id}/executions
```

The request chooses the server-defined Run operation (`execute` or `rollback`) and an idempotency key. It does not choose an arbitrary tool implementation.

## Failure and replay semantics

- Repeating an execution-start idempotency key returns the existing Run.
- Re-executing an already terminal Run returns the persisted result and Artifact.
- Run lease, Action status, Artifact, Case status and Domain Events commit under the active fencing token.
- Connector verification failure marks both Action and Run failed and always releases the lease.
- A monitor execution transitions to `monitoring`; rollback physically disables its Artifact and transitions the Action to `rolled_back`.
- Audit exports are archived rather than merely changing a database flag.
- External Connector execution is rejected before any Commerce Run is created.
- Connector outputs are verified by deterministic read-back; an exception is not swallowed or converted into success.

## Verification

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/actions/test_internal_connectors.py \
  tests/commerce/actions/test_action_execution.py

8 passed, 1 unrelated LangGraph warning
exit code: 0
```

The full deterministic Commerce gate also passed:

```text
396 passed, 22 real-model tests deselected
exit code: 0
```

Execution and rollback are deterministic business/infrastructure operations. They intentionally make no LLM request and therefore have no model identity, Provider Request ID or Token charge.

## Known limits

- Only local/internal reversible Connectors are executable.
- No real merchant ads, catalog, order-management or logistics write Connector is enabled.
- Crash recovery is covered through persisted Run/lease/idempotency semantics, but production multi-process reconciliation and fault-injection soak testing remain pending.
- Artifacts are verified on the local storage implementation; object-store and production retention-policy integration remain pending.
