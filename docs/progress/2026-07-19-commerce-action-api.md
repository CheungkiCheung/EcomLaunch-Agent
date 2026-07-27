# Commerce Action / Approval API

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: deterministic Action, Policy and Approval contracts complete

## Outcome

Commerce Case can now create and query evidence-backed Actions without deriving state from chat text:

```text
Supported Hypothesis + Evidence
→ Action Validator
→ server-owned Risk / Policy / Connector decision
→ persisted Action
→ optional Approval
→ approve / reject / modify
→ immutable audit events
```

HTTP contracts:

```text
POST /api/commerce/cases/{case_id}/actions
GET  /api/commerce/cases/{case_id}/actions
GET  /api/commerce/actions/{action_id}
GET  /api/commerce/actions/{action_id}/approval

POST /api/commerce/actions/{action_id}/approvals/approve
POST /api/commerce/actions/{action_id}/approvals/reject
POST /api/commerce/actions/{action_id}/approvals/modify
```

The service validates Workspace/Case ownership, Evidence and Hypothesis membership, expected-signal Metric references, risk, policy level, approval requirement, execution-tool binding and rollback completeness. FastAPI routes delegate to the application service; they do not contain business policy.

## Safety and state contracts

- Workspace is required on every read and mutation.
- Actor identity is persisted in approval/audit events.
- Action IDs, Policy decisions and Approval IDs are server-owned.
- Idempotency reuses the existing Action or decision instead of creating duplicates.
- High-risk or policy-blocked work cannot bypass Approval.
- Reject and modify are explicit state transitions, not edits to historical records.
- External merchant mutations remain fail closed even if a client submits an apparently valid payload.
- Rollback metadata is required before an executable Action may pass validation.

## Verification

Focused deterministic gate:

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/actions/test_validator_policy.py \
  tests/commerce/actions/test_approval.py \
  tests/commerce/api/test_action_router.py

11 passed, 1 unrelated LangGraph warning
exit code: 0
```

Current full deterministic Commerce regression:

```text
PYTHONPATH=. .venv/bin/pytest -q -m 'not real_model' tests/commerce

396 passed, 22 real-model tests deselected
1 unrelated LangGraph warning
exit code: 0
```

This slice is deterministic and does not call an LLM. It is therefore intentionally not assigned a model identity, Provider Request ID, Token cost or Latency record. The fresh Action Planner that creates a validated Action from verified context is documented separately.

## Known limits

- Workspace membership still uses the explicit Commerce header contract; production authentication/authorization integration remains pending.
- External merchant Connectors are not implemented and cannot execute.
- The React Action Center and browser interaction gate are not implemented.
- Approval WAIT is persisted in the Action lifecycle, but a generalized Lead-loop approval-resume UX is still pending.
