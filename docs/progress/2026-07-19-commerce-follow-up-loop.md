# Commerce Follow-up Loop

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: deterministic new-data assessment and Case close/reopen semantics complete

## Outcome

An executed Action can now be checked against newly uploaded data without pretending that correlation proves an Action effect:

```text
Action expected signal
→ new immutable Dataset / Analysis snapshot
→ deterministic Metric recomputation
→ signal target_met / target_not_met / unknown
→ causal evidence check
→ Follow-up outcome
→ Case close / reopen / continue investigating
```

HTTP contracts:

```text
POST /api/commerce/actions/{action_id}/follow-ups
GET  /api/commerce/actions/{action_id}/follow-ups
```

The Follow-up Run, assessment, MetricObservation and Action/Case transitions are persisted and replayable. A reliable controlled intervention plus comparison evidence is required before any causal effect claim; the current public Gold Case flow does not provide that evidence and therefore remains `inconclusive` even when the target signal improves.

## Boundary behavior

- Metric direction and threshold come from the validated Action, not model prose.
- Insufficient sample size is explicit and keeps the signal unknown.
- A met target can resolve the Case while the Action effect remains causally inconclusive.
- A missed target can reopen or continue the Case.
- Follow-up is idempotent and Workspace scoped.
- The assessment stores limitations and `causal_claim=false` when no reliable counterfactual exists.
- No GMV, CTR, ROI, profit, inventory or other unavailable private metric is invented.

## Verification

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/actions/test_follow_up.py

4 passed, 1 unrelated LangGraph warning
exit code: 0
```

The focused tests cover target met, target missed, insufficient sample, HTTP execution/listing, persisted Follow-up reads, Case resolution/reopen behavior and the causal-uncertainty guard. The current full deterministic Commerce regression is `396 passed, 22 real-model tests deselected`.

This stage recomputes deterministic metrics and does not invoke an LLM. It therefore has no model identity, Provider Request ID, Token or model Latency record.

## Known limits

- Follow-up is currently triggered explicitly through the API; a production scheduler or data-arrival subscription is not implemented.
- The first public data flow has no experimental treatment/control contract, so Action effectiveness remains honestly `inconclusive`.
- The frontend Follow-up page, notifications and browser QA are pending.
- Long-running monitoring and late-arriving-data watermark policies still need production hardening.
