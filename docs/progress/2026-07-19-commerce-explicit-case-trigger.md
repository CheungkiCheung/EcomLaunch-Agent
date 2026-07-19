# Commerce Case Agent - Explicit User Case Trigger

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic trigger/API slice verified
> Model requests: none; this slice is intentionally deterministic

## Outcome

Users no longer need a detected temporal anomaly before opening a Commerce Case.
The new explicit Case path accepts seller identity, baseline/current windows, one
to three requested evidence Paths, and an outcome-agnostic `PeerCohortPolicy`
when SellerPeer is requested.

```text
explicit user request
→ deterministic seller MetricSnapshots
→ Case with no fabricated anomaly Evidence
→ immutable CaseLineage
→ SHA-256-verified case-context Artifact
→ structured case.created trigger payload
→ DynamicPathRouter requested Paths
```

The API is `POST /api/commerce/datasets/{dataset_id}/cases`. The response
returns the Case, structured trigger and analysis windows. The raw user prompt
is not stored in the trigger Artifact.

## Evidence Discipline

- Explicit Cases have empty `anomaly_ids` and empty anomaly-derived metric IDs.
- Baseline/current deterministic snapshots remain available as context.
- Background metrics are not route signals; only real anomalies or explicit
  requested Paths select a Path.
- Requesting SellerPeer without a Peer Policy fails validation.
- Peer eligibility remains independent of late-delivery outcome.
- `case.created` carries a structured trigger so the frontend does not infer
  creation intent from title or chat text.

## TDD

Initial RED:

```text
ImportError: cannot import name 'CaseTriggerType'
```

GREEN introduced `CaseTriggerType`, `CaseTriggerDigest`, explicit Case service,
API schemas/router, lineage support for non-anomaly Cases and trigger-aware
routing.

A later RED proved that reading every background MetricSnapshot name as a route
signal incorrectly selected Fulfillment for an explicit Review-only Case. The
router now reads metric route signals only from persisted anomaly records;
explicit requested Paths are handled separately.

## Verification

```text
focused contracts: 20 passed
full deterministic Commerce regression: 247 passed
unrelated LangChain pending-deprecation warnings: 1
exit code: 0
```

Commerce Ruff and `git diff --check` passed. All nine live provider tests were
explicitly excluded because this slice contains no LLM behavior.

## Architecture Follow-up

ADR 0005 selects DeerFlow as the primary Harness. The trigger is the durable
routing input for the upcoming `CommerceSubagentAdapter`; it is not an excuse to
keep extending role-specific Worker calls.
