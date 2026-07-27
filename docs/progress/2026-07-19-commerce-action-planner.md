# Fresh DeepSeek V4 Action Planner

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: fresh verified planning gate complete

## Outcome

Commerce can now turn fresh, persisted and verified diagnosis state into a bounded internal Action proposal:

```text
persisted Case / Evidence / supported Hypothesis
→ fresh Context reconstruction
→ fresh DeepSeek V4 Verification
→ fixed Action Catalog prompt
→ fresh DeepSeek V4 Action Planner
→ strict parser
→ deterministic Catalog materialization
→ Validator + Policy
→ persisted Action / Approval
→ free idempotent replay
```

Endpoint:

```text
POST /api/commerce/cases/{case_id}/action-plans
```

The model may choose only:

```text
no_op
export_audit_cohort
create_internal_task
create_metric_monitor
request_missing_data
```

The model cannot author `external_mutation`, risk/policy level, Approval, Connector, execution tool, rollback plan, Workspace/Case/Action IDs, or monitor comparison/threshold. Those fields remain server-owned. Evidence, Hypothesis and Metric IDs must belong to the fresh Case context.

## Current fresh live evidence

Command:

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/actions/test_action_planner_live.py \
  -m real_model \
  --basetemp=../.deer-flow/commerce/evaluation/live-test-artifacts/action-planner

1 passed, 1 unrelated LangGraph warning
exit code: 0
pytest wall time: 10.10s
```

Fresh Verification preflight:

```text
run_id: preflight-d635eb762d634efbb6d02ab4b0ceba86
provider_request_id: 77c55b4f-e4fb-426b-a037-761d040c2cb9
actual_model_identity: deepseek-v4-flash
tokens: 59 input / 11 output / 70 total
latency: 1310.55 ms
attempts: 1
retry: 0
stop_reason: stop
```

Fresh Verification:

```text
run_id: verification-44288e58884c46039049bb4a767d9db3
provider_request_id: 4c86d011-8693-432f-8a2f-84e42e854eac
actual_model_identity: deepseek-v4-flash
tokens: 5565 input / 212 output / 5777 total
latency: 3215.76 ms
attempts: 1
retry: 0
stop_reason: stop
role/profile: verifier / strong_verifier
```

Action Planner preflight:

```text
run_id: preflight-3ee22cca67764e37952706b8b8717051
provider_request_id: a63aba8b-1adc-4c01-a034-1d22f308c36a
actual_model_identity: deepseek-v4-flash
tokens: 58 input / 11 output / 69 total
latency: 796.68 ms
attempts: 1
retry: 0
stop_reason: stop
```

Action Planner:

```text
run_id: action-plan-case_265288e1a6dd5d668411f097a5dd1993-d20c87d57d29463797d8814cf5bfd6a3
provider_request_id: 4ae39fa6-3c94-463c-bc02-8693b7620823
actual_model_identity: deepseek-v4-flash
tokens: 4052 input / 342 output / 4394 total
latency: 3369.40 ms
attempts: 1
retry: 0
stop_reason: stop
role/profile: action_planner / fast_structured
prompt: commerce-action-planner@1.0.0
skill/catalog: commerce-action-catalog@1.0.0
```

The accepted model chose `create_metric_monitor`. The server derived the baseline threshold, `less_than_or_equal` comparison, `disable_metric_monitor` rollback, Action ID, Case/Workspace ownership and Policy decision. The same idempotency key then returned the same Action with `planning=null`, wrote no second audit and made no second model request.

Deterministic Catalog tests:

```text
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/actions/test_action_planner.py

2 passed, 1 unrelated LangGraph warning
exit code: 0
```

## Known limits

- The first Catalog is intentionally internal-only and small.
- Planner usefulness has one fresh integrated gate; broader repeated Gold Case experiments remain pending.
- The model output still contains a natural-language title/description, but all execution-relevant authority remains deterministic.
- The frontend Action Center and human approval UX are pending.

