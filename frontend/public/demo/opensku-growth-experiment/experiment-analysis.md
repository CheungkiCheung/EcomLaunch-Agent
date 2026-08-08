# Sample Experiment Analysis — Checkout Social Proof

> Deterministic OpenSKU demo fixture. No model, store account, external file, or network source is used by this recorded analysis.

## Business question

Should the checkout social-proof treatment be shipped based on purchase conversion?

## Registered sample inputs

| Fixture                      | Join key     | Purpose                                             |
| ---------------------------- | ------------ | --------------------------------------------------- |
| `visitors.csv`               | `visitor_id` | Eligible visitor population and exposure timestamp  |
| `experiment_assignments.csv` | `visitor_id` | Control/treatment assignment                        |
| `orders.csv`                 | `visitor_id` | Binary purchaser outcome during the analysis window |

The live Growth Analyst registers uploaded CSV/XLSX files as bounded DuckDB tables. Application tools allow read-only `SELECT` / `WITH` queries and reject external file access, multiple statements, network access, and write operations.

## Join contract

```sql
WITH purchaser AS (
  SELECT DISTINCT visitor_id
  FROM orders
  WHERE order_status = 'completed'
)
SELECT
  a.variant,
  COUNT(*) AS assigned_visitors,
  COUNT(p.visitor_id) AS purchasers
FROM experiment_assignments AS a
JOIN visitors AS v USING (visitor_id)
LEFT JOIN purchaser AS p USING (visitor_id)
GROUP BY a.variant;
```

Recorded aggregate result:

| Variant   | Assigned visitors | Purchasers | Conversion rate |
| --------- | ----------------: | ---------: | --------------: |
| Control   |             1,200 |         96 |        0.080000 |
| Treatment |             1,180 |        124 |        0.105085 |

## Two-proportion z-test

The fixture uses a two-sided pooled two-proportion z-test for the binary purchase outcome.

```text
absolute lift       = 0.105085 - 0.080000 = 0.025085
relative lift       = 0.025085 / 0.080000 = 31.36%
z statistic         = 2.1125
two-sided p-value   = 0.0346
95% CI, abs. lift   = [0.001809, 0.048361]
                     = [+0.18 pp, +4.84 pp]
```

## Sample ratio mismatch

For a predeclared 50/50 allocation, the observed split is 1,200 control and 1,180 treatment visitors.

```text
chi-square statistic = 0.1681
SRM p-value           = 0.6818
result                = PASS
```

This check does not prove the experiment is unbiased; it only indicates that the aggregate allocation does not show a statistically unusual departure from the expected split.

## Decision contract

- **SHIP:** primary threshold passes, the confidence interval excludes zero in the desired direction, SRM passes, and guardrails are acceptable.
- **EXTEND:** direction is promising but uncertainty, power, or data quality is insufficient.
- **STOP:** effect is harmful, the decision threshold clearly fails, or the experiment data is invalid.

Fixture result: **SHIP WITH MONITORING**.
