# Commerce Case Agent Phase 3 — Read API Slice

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: read slice complete; Phase 3 API exit criteria not complete
> Model requests: `0`

## Outcome

The first Commerce HTTP surface is now a deterministic Dataset intake plus a read-only Case Workspace. It is mounted only when `COMMERCE_CASE_AGENT_ENABLED=true`:

- `POST /api/commerce/datasets/intake`
- `GET /api/commerce/datasets/{dataset_id}/profile`
- `GET /api/commerce/datasets/{dataset_id}/capabilities`

- `GET /api/commerce/cases`
- `GET /api/commerce/cases/{case_id}`
- `GET /api/commerce/cases/{case_id}/evidence`
- `GET /api/commerce/cases/{case_id}/evidence/{evidence_id}`
- `GET /api/commerce/cases/{case_id}/hypotheses`
- `GET /api/commerce/cases/{case_id}/events`

The Dataset endpoints call the existing safe Intake, Profiler, Semantic Mapper and Capability Registry. The Case endpoints read from the same application-owned Case, Evidence, Hypothesis and Domain Event repositories already covered by SQLite persistence tests. It does not create an alternate chat-derived state or reimplement deterministic business rules in the router.

## Boundary and safety

Every request carries `X-Commerce-Workspace-Id`; all repository reads include that Workspace in their predicates. A Case, Evidence or Event from another Workspace is not exposed; a Case/Evidence path mismatch returns 404. Invalid typed identifiers return 400. Missing persistence returns explicit 503. The router is absent from the Gateway route table when the feature flag is false.

This header is an explicit stage contract, not a finished multi-tenant authorization model. The authenticated user → Workspace membership mapping is still missing. Therefore the Commerce feature flag remains disabled by default and must not be enabled in a multi-tenant production deployment until membership authorization is implemented.

## Deterministic TDD evidence

The initial read API contract test failed during collection because `app.commerce.api.dependencies` and the read router did not exist:

```text
ModuleNotFoundError: No module named 'app.commerce.api.dependencies'
exit code: 2
```

After implementing the minimum service, schemas, router and feature-flag mount:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/api/test_read_router.py \
  tests/test_commerce_feature_flag.py

7 passed
exit code: 0
```

The tests seed a real SQLite Commerce schema through `SqlCommerceUnitOfWork`, then exercise the HTTP adapter against that persisted Case, Evidence, Hypothesis and Domain Event stream. They make no model calls.

The Dataset intake contract then used a real multipart request and a real temporary storage root. It passed the existing `DataIntakeService` safety checks and deterministically returned the Profile, Mapping and Capability objects:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/api/test_data_intake_router.py \
  tests/test_commerce_feature_flag.py

7 passed
exit code: 0
```

## Not yet included

- Anomaly-to-Case application service;
- Investigation Start;
- Run Detail / Run Event API;
- authenticated Workspace membership;
- Agent or LLM behavior.

The last items remain intentionally separate from this read-only adapter. Any future Agent or LLM test must make a fresh, identity-verified DeepSeek V4 request and must stop on unavailable model, unverifiable identity or exhausted quota.
