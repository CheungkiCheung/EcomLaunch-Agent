# Commerce Case Agent — Explicit Case Data Lineage

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic Case lineage complete
> Model requests: `0`

## Outcome

Every newly detected anomaly Case now carries an explicit immutable link back to the exact Dataset analysis context needed by a future Agent executor.

Persisted lineage includes:

- Workspace, Case and Dataset IDs;
- seller entity ID and external key;
- baseline and current windows;
- Anomaly IDs;
- MetricObservation IDs;
- relative `derived/case-context-*.json` path;
- artifact SHA-256 and schema version.

The context artifact contains the deterministic baseline/current MetricSnapshots, anomaly signals and Capability Profile used to create the Case. It is written read-only before the database transaction and referenced by SHA-256.

Case creation and lineage insertion occur in the same SQL transaction as `case.created`. Existing pre-lineage Cases can be backfilled by rerunning the same deterministic analysis, which appends `case.lineage_attached` without changing the Case projection version.

## API

Case Detail now includes optional `lineage`, and the explicit endpoint is:

```text
GET /api/commerce/cases/{case_id}/lineage
```

Both are Workspace-scoped. Manually created Cases without data lineage return `null` in Case Detail and 404 from the dedicated endpoint instead of guessing a Dataset.

## Validation

Tests cover safe relative artifact paths, ordered non-overlapping windows, ORM/migration compatibility, anomaly-to-lineage persistence, real artifact existence, idempotent repeated analysis, Case Detail serialization and Workspace isolation.

Full deterministic Commerce regression:

```text
218 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed. No model request was made because this milestone is deterministic lineage and storage work.

## Next

Build the initial ContextPacket loader that verifies the lineage artifact SHA-256, reloads the Dataset Capability Profile, selects the relevant Evidence digests and creates the first safe Checkpoint before any real DeepSeek V4 Path Agent request.
