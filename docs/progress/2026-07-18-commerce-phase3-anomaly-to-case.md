# Commerce Case Agent Phase 3 — Deterministic Anomaly-to-Case

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: complete for deterministic analysis slice
> Model requests: `0`

## Outcome

`CommerceAnalysisService` closes the first real product path without an LLM:

```text
uploaded Dataset
  → immutable Manifest + explicit Semantic Mapping
  → Olist normalized Facts
  → baseline/current MetricSnapshot
  → AnomalyDetector
  → deterministic CaseCandidate
  → Case + Evidence + Domain Events in one UoW
  → Replayable Case Event Stream
```

The endpoint is:

```text
POST /api/commerce/datasets/{dataset_id}/analyze
```

The request supplies baseline/current half-open windows and may scope one seller. Without a seller filter the service scans all normalized sellers, returning explicit skipped-seller reasons for data that cannot support a calculation.

## Persistence and traceability

- a Dataset-scoped fingerprint-derived Case ID makes repeated scans idempotent without colliding across Datasets;
- each AnomalySignal produces deterministic Evidence ID derived from Case ID + signal ID;
- Evidence references both baseline and current MetricObservation IDs;
- Case, Evidence and `evidence.appended` Event commit atomically;
- `case_version` in record events makes Replay reconstruct the final Case version;
- metric snapshots and signal IDs are stored as immutable, read-only derived JSON under the Dataset;
- no causal claim is made from the anomaly signal, and no private metric is invented.

## Frozen real-data verification

The test uses the real GC-FULFILLMENT-001 Olist fixture and the frozen windows:

```text
baseline: 2017-12-02 → 2018-01-31
current: 2018-01-31 → 2018-04-01
seller: 4869f7a5dfa277a7dca6462dcf3b52b2
```

It observes deterministic late-delivery, transit-time and review-score anomaly signals, persists the Case and Evidence records, verifies event Replay, writes a derived artifact, then repeats the scan to verify no duplicate Case/Event stream.

## TDD and verification evidence

```text
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/api/test_analysis_service.py

2 passed
exit code: 0
```

The broader deterministic Commerce regression after this slice is `173 passed` with one unrelated LangChain pending-deprecation warning. Live model tests remain separate; this analysis path intentionally makes zero model requests.

## Remaining boundary

- authenticated Workspace membership;
- Action / Approval / Follow-up persistence;
- Investigation Start and Run Event API;
- PostgreSQL live integration;
- Agent Goal Loop and Verification.
