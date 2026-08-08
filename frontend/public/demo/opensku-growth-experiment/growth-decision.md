# Sample Growth Decision — Checkout Social-Proof Experiment

> Recorded OpenSKU demo fixture. The counts and metrics below are deterministic sample data created to demonstrate the Growth Analyst workflow. They are not results from a real store and must not be used as a production rollout decision.

## Recommendation

**SHIP WITH MONITORING**

The treatment increased purchase conversion from **8.00%** to **10.51%** in the recorded fixture. The absolute lift is **+2.51 percentage points**, the relative lift is **+31.36%**, and the two-sided two-proportion z-test returns **p = 0.0346**.

The 95% confidence interval for the absolute lift is **+0.18 to +4.84 percentage points**, and the equal-allocation sample-ratio-mismatch check passes with **p = 0.682**.

## Decision table

| Metric              | Control | Treatment | Difference |
| ------------------- | ------: | --------: | ---------: |
| Assigned visitors   |   1,200 |     1,180 |        -20 |
| Purchasers          |      96 |       124 |        +28 |
| Purchase conversion |   8.00% |    10.51% |   +2.51 pp |
| Relative lift       |       — |         — |    +31.36% |

## Why this is a Ship decision

1. The primary metric uses the predeclared binary purchase outcome.
2. The two-sided p-value is below the fixture threshold of 0.05.
3. The 95% confidence interval for absolute lift remains above zero.
4. The observed assignment split does not indicate sample ratio mismatch.
5. The recommendation remains bounded by rollout guardrails rather than treating one experiment as permanent proof.

## Rollout guardrails

- Release to 25% of eligible traffic for one business cycle before full rollout.
- Monitor refund rate, average order value, checkout latency, and customer-support contacts.
- Stop the rollout if any guardrail crosses its predeclared limit.
- Re-run the analysis after the first staged rollout window and compare the effect direction and interval.

## What would change this decision

The recommendation should move to **EXTEND** if the original assignment or exposure logs are incomplete, if the metric definition changed during the test, or if a material guardrail deteriorates. It should move to **STOP** if a reproducible data-quality issue invalidates the assignment or purchase counts.
