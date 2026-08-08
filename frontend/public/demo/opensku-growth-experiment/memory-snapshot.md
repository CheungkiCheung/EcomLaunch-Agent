# Sample Business Memory Snapshot

> Recorded OpenSKU demo fixture. This document illustrates the bounded facts that a live Growth Analyst conversation may retain across sessions. It contains no real company or customer data.

## Memory namespace

```text
workspace: recorded-demo
business: hypothetical-store
analysis: checkout-social-proof-2026-08
```

## Retained metric context

| Key               | Recorded value          | Boundary                   |
| ----------------- | ----------------------- | -------------------------- |
| Primary metric    | Purchase conversion     | Fixture definition         |
| Control           | 96 / 1,200 = 8.00%      | Deterministic sample count |
| Treatment         | 124 / 1,180 = 10.51%    | Deterministic sample count |
| Absolute lift     | +2.51 percentage points | Calculated from fixture    |
| Relative lift     | +31.36%                 | Calculated from fixture    |
| Two-sided p-value | 0.0346                  | Two-proportion z-test      |
| SRM p-value       | 0.6818                  | Expected 50/50 allocation  |
| Decision          | SHIP WITH MONITORING    | Fixture recommendation     |

## Retained conclusion

The checkout social-proof treatment passed the recorded primary conversion threshold and sample-ratio check. Stage the rollout and monitor refund rate, average order value, checkout latency, and support contacts before treating the result as durable.

## Deliberately not retained

- Raw visitor- or order-level rows
- Personal identifiers
- Credentials or external file locations
- Claims that the fixture represents a real store
- A permanent causal conclusion beyond the recorded experiment window

## Example follow-up

> “What did we decide about the checkout social-proof experiment?”

Expected bounded recall:

> “In the recorded fixture, the decision was Ship with Monitoring: treatment conversion was 10.51% versus 8.00% control, with p = 0.0346 and SRM p = 0.6818. The staged rollout still needs refund-rate, AOV, latency, and support guardrails.”
