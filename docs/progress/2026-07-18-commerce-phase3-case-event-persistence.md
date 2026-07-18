# Commerce Case Agent Phase 3 — Case and Domain Event Persistence

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: first persistence substage complete; Evidence / Hypothesis substage follows in a separate record
> Model requests: `0`

## Outcome

Commerce now has an application-owned persistence boundary for Case state and Domain Events. The implementation reuses DeerFlow's async SQLAlchemy Engine / Session Factory but does not register Commerce models in the reusable Harness metadata. State mutation and event append are committed atomically so the Case database and the frontend's future authoritative event stream cannot diverge through a partial write.

Implemented:

- `CommerceBase` with independent SQLAlchemy metadata;
- `commerce_cases` and `commerce_domain_events` ORM tables;
- SQLite and PostgreSQL-compatible DDL;
- independent Alembic environment and revision branch;
- independent `commerce_alembic_version` table;
- Workspace-scoped `CaseRepository` Protocol;
- SQL Case Create / Get / List / status-filter / Save;
- optimistic concurrency through `expected_version`;
- immutable Domain Event envelope with schema version;
- strong `TraceId` and `CorrelationId` contracts;
- independent Case and Run aggregate sequences;
- trace, correlation and causation metadata;
- idempotent append for the same Event ID and payload;
- explicit rejection when an Event ID is reused for different data;
- bounded sequence-conflict retry;
- ordered Case and Run event reads;
- `SqlCommerceUnitOfWork` for atomic Case + Event writes;
- `case.created`, `case.status_changed`, `case.reopened` and `case.updated` event typing;
- deterministic Case projection replay.

## Persistence boundary

```text
deerflow.persistence.engine
        │ shared AsyncEngine / Session Factory
        ▼
app.commerce.persistence
  ├── CommerceBase metadata
  ├── commerce_cases
  ├── commerce_domain_events
  ├── SqlCaseRepository
  ├── SqlDomainEventStore
  └── SqlCommerceUnitOfWork
```

The dependency remains:

```text
app.* → deerflow.*
deerflow.* -X→ app.*
```

Commerce has an independent migration history, not an independent database pool. This preserves one configured SQLite/PostgreSQL backend while preventing the Harness migration package from importing application business models.

## Atomic mutation rule

Standalone Repository reads are safe. Production Case mutations should go through `SqlCommerceUnitOfWork`:

```text
BEGIN
  UPDATE commerce_cases WHERE version = expected_version
  INSERT commerce_domain_events with next case_sequence
COMMIT
```

If optimistic concurrency or event sequencing fails, the transaction rolls back both writes. A stale writer cannot change the Case, and it cannot leave a misleading event behind.

## Event ordering

Every Event belongs to at least one aggregate:

- Case only: gets `case_sequence`;
- Run only: gets `run_sequence`;
- Case + Run: gets both sequences in the same event.

Sequences are Workspace-scoped and aggregate-local. A focused SQLite concurrency test created a Case and then appended eight updates concurrently; the final persisted stream was exactly `1..9`, with no duplicate or missing value.

## Migration entry

```text
cd backend
PYTHONPATH=. .venv/bin/python -m app.commerce.persistence.migrations \
  upgrade --url "sqlite+aiosqlite:////absolute/path/to/deerflow.db"
```

The migration test starts from an empty SQLite database and verifies that the independent entry creates only:

```text
commerce_alembic_version
commerce_cases
commerce_domain_events
```

## TDD evidence

The first focused run failed during collection because the Domain Event and Persistence modules did not exist:

```text
ModuleNotFoundError: No module named 'app.commerce.domain.events'
ModuleNotFoundError: No module named 'app.commerce.persistence.repositories'
ModuleNotFoundError: No module named 'app.commerce.persistence.base'
exit code: 2
```

The first concurrent event test then exposed a real sequence race:

```text
UNIQUE constraint failed:
commerce_domain_events.case_id,
commerce_domain_events.case_sequence
```

The store was changed to retry the entire append transaction with a bounded budget. The concurrency test then passed with contiguous sequences.

## Focused verification

```text
cd backend
.venv/bin/pytest -q \
  tests/commerce/domain/test_domain_events.py \
  tests/commerce/persistence

16 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full Commerce deterministic regression, with live model validation kept separate:

```text
.venv/bin/pytest -q tests/commerce \
  --ignore=tests/commerce/evaluation/test_real_model_preflight_live.py \
  tests/test_commerce_feature_flag.py

156 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static verification:

```text
.venv/bin/ruff check \
  app/commerce \
  tests/commerce \
  tests/test_commerce_feature_flag.py \
  ../scripts/commerce_data/build_olist_gold_cases.py

All checks passed
exit code: 0
```

## Known boundary

- SQLite repository, migration, concurrency and replay paths were executed locally.
- PostgreSQL SQLAlchemy DDL was compiled for both tables, but no live PostgreSQL instance was used in this substage.
- Evidence / Hypothesis persistence is documented in [`2026-07-18-commerce-phase3-evidence-hypothesis-persistence.md`](./2026-07-18-commerce-phase3-evidence-hypothesis-persistence.md); Action, Approval and Follow-up repositories are not implemented yet.
- Commerce API and feature-flagged router are not implemented yet.
- No Agent behavior was tested; future Agent tests still require a fresh real DeepSeek V4 request.

## Next

Continue Phase 3 with Action / Approval / Follow-up persistence, then expose Case, Evidence, Hypothesis and Event read contracts through the feature-flagged Commerce API.
