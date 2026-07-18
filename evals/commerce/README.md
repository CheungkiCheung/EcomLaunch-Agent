# Commerce Gold Cases

This directory contains small, reproducible evaluation fixtures derived from the real Olist Brazilian E-Commerce Public Dataset.

They are public benchmark fixtures, not live merchant telemetry. They cannot prove merchant GMV, CTR, CVR, ROI, ad spend, inventory, profit, or causal business uplift.

## Cases

| Case | Purpose | Frozen input |
|---|---|---|
| `GC-FULFILLMENT-001` | Separate seller handling from carrier transit degradation and preserve an inconclusive causal follow-up | 554 delivered, single-seller orders for one real anonymized seller |
| `GC-REVIEW-002` | Diagnose review experience degradation while late-delivery rate remains zero | 35 delivered, single-seller orders for one real anonymized seller |
| `GC-CAPABILITY-003` | Prove capability-aware degradation after review data is removed | Same non-review rows as `GC-FULFILLMENT-001`, without `order_reviews.csv` |
| `GC-PEER-004` | Compare one delivery outlier against an outcome-agnostic matched seller cohort | 316 delivered orders across 6 real anonymized sellers in one pure category, seller state and time window |

## On-disk isolation

Each case has four layers:

```text
case-metadata.json       # id, key, version, title
input-bundle.json        # Agent-visible manifest and prompt
input/*.csv              # Agent-visible real public rows
expected-behavior.json   # evaluator-only facts, routes and forbidden claims
provenance.json          # evaluator-only source, hashes and selection rule
```

Only `input-bundle.json` and the listed `input/*.csv` files may be passed to an Agent. The expected behavior and provenance files are not part of Agent context.

The loader verifies every input file's path, SHA-256, row count and ordered columns before returning an `EvaluationCase`.

## Rebuild

The full Olist CSV set is intentionally outside Git. With the frozen source files under `/tmp/olist-kaggle`:

```bash
python3 scripts/commerce_data/build_olist_gold_cases.py
```

The builder:

1. validates the raw Olist SHA-256 values;
2. selects delivered orders in frozen purchase-time windows;
3. excludes multi-seller orders so order-level reviews are not attributed ambiguously;
4. writes only the required rows and tables;
5. normalizes only CSV cell line endings and trailing cell whitespace for Git-safe deterministic fixtures;
6. recomputes frozen metrics and fails on drift;
7. writes deterministic manifests and evaluator-only contracts.

For `GC-PEER-004`, cohort eligibility is frozen before looking at the late-delivery value:

- purchase time from 2018-01-01 inclusive to 2018-07-01 exclusive;
- product category exactly `fashion_bolsas_e_acessorios` for every item in the order;
- seller state `SP`;
- delivered, single-seller orders with eligible delivery timestamps;
- at least 20 eligible orders per seller.

The target has 59 eligible orders and 16 late deliveries. The five peers have 257 eligible orders and 19 late deliveries in total. The peer metric is the pooled order-level rate (`19 / 257`), not an unweighted average of seller percentages. This comparison controls several visible dimensions but still cannot establish causal seller responsibility.

## Deterministic verification

```bash
cd backend
PYTHONPATH=. uv run pytest tests/commerce/fixtures/test_gold_cases.py -v
```

This verification does not invoke a model. Future Agent and semantic evaluation runs must use a fresh, identity-verified DeepSeek V4 request and cannot use replay or fake model responses.

## License and attribution

Source: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

Kaggle metadata reports `CC BY-NC-SA 4.0`. These small derived fixtures are retained for research, portfolio and reproducibility purposes with attribution. They must not be presented as commercial merchant data or redistributed as a substitute for the full dataset.
