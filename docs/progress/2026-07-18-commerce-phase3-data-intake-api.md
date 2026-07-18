# Commerce Case Agent Phase 3 — Data Intake / Profile / Capability API

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: complete for deterministic data slice
> Model requests: `0`

## Outcome

The feature-flagged Commerce HTTP surface now accepts real heterogeneous files and runs the existing deterministic data pipeline:

```text
multipart files
  → safe DataIntakeService
  → immutable raw storage + manifest
  → DataProfiler
  → SemanticMapper + Workspace confirmations
  → CapabilityRegistry
```

Endpoints:

- `POST /api/commerce/datasets/intake`
- `GET /api/commerce/datasets/{dataset_id}/profile`
- `GET /api/commerce/datasets/{dataset_id}/capabilities`

The upload endpoint returns the Manifest, Profile, current Semantic Mapping and Capability Profile together. Later reads reconstruct these views from the saved Manifest, so the API does not maintain a second mutable copy of data facts.

## Safety and tenancy boundaries

- Uploads must provide plain filenames; path-like names are rejected before storage;
- each upload is size-bounded and written into a temporary staging directory;
- the existing Intake service rejects symlinks, unsafe ZIP paths, duplicate members, unsupported formats and compression bombs;
- raw files and `manifest.json` remain read-only after Intake;
- Dataset lookup constructs a path only from validated `WorkspaceId` and `DatasetId` values;
- a Dataset from another Workspace returns 404;
- feature flag false means no Commerce route is mounted.

The current `X-Commerce-Workspace-Id` header is an explicit stage contract, not a finished authentication-to-Workspace membership check. Keep the feature flag disabled for multi-tenant production until membership authorization exists.

## TDD and verification evidence

The initial Data API contract failed during collection because `CommerceDataService` did not exist:

```text
ModuleNotFoundError: No module named 'app.commerce.api.data_service'
exit code: 2
```

After implementing the file-backed application service, response schema and router endpoints:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/api/test_data_intake_router.py \
  tests/test_commerce_feature_flag.py

7 passed
exit code: 0
```

The current Commerce deterministic regression is:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce \
  --ignore=tests/commerce/evaluation/test_real_model_preflight_live.py \
  tests/test_commerce_feature_flag.py

167 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

No model request was made. Upload/Profile/Capability behavior is deterministic and does not constitute Agent behavior validation. Future Agent or LLM tests remain gated by a fresh identity-verified DeepSeek V4 request.

## Remaining Phase 3 boundary

- Anomaly-to-Case application service;
- Investigation Start;
- Run Detail / Run Events;
- authenticated Workspace membership;
- PostgreSQL live integration test.
