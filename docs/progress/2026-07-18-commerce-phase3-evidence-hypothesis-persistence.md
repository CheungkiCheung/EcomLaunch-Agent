# Commerce Case Agent Phase 3 — Evidence and Hypothesis Persistence

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: complete
> Model requests: `0`

## Outcome

The Case persistence boundary now keeps the two core investigation records durable and auditable without making an LLM part of the storage contract:

- `commerce_evidence` stores immutable, Case-scoped Evidence;
- `commerce_hypotheses` stores immutable, contiguous Hypothesis versions;
- both tables belong to the application-owned `CommerceBase` metadata;
- migration `20260718_0002` extends the independent `commerce_alembic_version` branch;
- no Commerce table or model is imported into the reusable DeerFlow Harness.

## Contracts

`SqlEvidenceRepository` supports:

- append-only IDs;
- idempotent append of the same immutable object;
- explicit `ImmutableRecordConflictError` for reused IDs with changed content;
- Workspace-scoped `get` and Case-scoped ordered listing;
- complete Fact and MetricObservation ID preservation.

`SqlHypothesisRepository` supports:

- version `1` as the first version;
- contiguous version allocation (`1, 2, 3, ...`);
- explicit `list_versions` and `get_latest` reads;
- `HypothesisVersionConflictError` for skipped versions;
- immutable conflict detection for reused `Hypothesis ID + Version`;
- complete Supporting and Contradicting Evidence ID preservation.

## Atomic Case / Record / Event mutation

Production writes go through `SqlCommerceUnitOfWork`:

```text
BEGIN
  INSERT commerce_evidence OR commerce_hypotheses
  UPDATE commerce_cases WHERE version = expected_version
  INSERT commerce_domain_events
COMMIT
```

The Unit of Work validates Workspace and Case ownership and requires the new record ID to be present in the Case membership tuple. Evidence writes emit `evidence.appended`; Hypothesis version writes emit `hypothesis.version_appended`. Both event payloads include `case_version`, record identity, semantic/status information and source Evidence IDs where applicable. If the Case optimistic-concurrency check or event sequence append fails, the record, Case and Event roll back together.

`replay_case_projection` treats these record events as first-class Case stream entries and advances the projected Case version from `case_version`; it does not confuse Hypothesis version with Case version.

## TDD and verification evidence

The focused RED run failed during collection because the planned `work_records`, `EvidenceRow` and `HypothesisRow` contracts did not exist:

```text
ModuleNotFoundError: No module named 'app.commerce.persistence.work_records'
ImportError: cannot import name 'EvidenceRow'
exit code: 2
```

After the minimum implementation and one migration branch-label correction:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/persistence/test_evidence_hypothesis_repository.py \
  tests/commerce/persistence/test_orm_models.py

7 passed
exit code: 0
```

The rollback regression was then added and passed:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/persistence/test_evidence_hypothesis_repository.py

5 passed
exit code: 0
```

Focused deterministic verification:

```text
.venv/bin/ruff check app/commerce tests/commerce
# All checks passed

PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/domain/test_domain_events.py \
  tests/commerce/persistence
# 20 passed; 1 unrelated LangChain pending-deprecation warning
```

No model request was made. This substage therefore provides no evidence about Lead, Path Agent, Router, Verification or any other LLM behavior. Those tests remain subject to the fresh, identity-verified DeepSeek V4 gate and must stop on unavailable model, unverified identity or exhausted quota.

## Known boundary

- PostgreSQL DDL compiles; a live PostgreSQL integration instance has not been run.
- Action, Approval and Follow-up persistence remain Phase 5 scope and are intentionally not modeled here.
- Commerce API, Agent loops and frontend Case Workspace remain unimplemented.
