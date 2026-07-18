# Commerce Case Agent Phase 1 — Domain Contract and Gold Cases

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Model requests: `0`

## Outcome

Phase 1 established the framework-independent Commerce domain contract and three real Olist Gold Case fixtures.

Implemented:

- `app.commerce` package boundary;
- stable enums and runtime-validated typed IDs;
- explicit Case state transitions;
- immutable `SourceRef`, `Fact`, `MetricObservation` and `Evidence`;
- immutable `Case`, `Hypothesis`, `Action`, `ApprovalRequirement` and `RollbackPlan`;
- high-risk Action approval gate;
- structurally isolated `InputBundle` and `ExpectedBehavior`;
- machine-readable Forbidden Claims and Capability Ablation;
- manifest-verifying Gold Case loader;
- SHA-pinned, deterministic Olist fixture builder;
- three small real-data fixtures under `evals/commerce/cases/`.

No Agent behavior was tested in this phase. All tests were deterministic and model-free.

## RED evidence

### Package boundary

```text
7 failed, 1 passed
reason: app.commerce and its subpackages did not exist
```

### Domain foundations

```text
collection error
reason: app.commerce.domain.enums did not exist
```

### Evidence chain

```text
collection error
reason: app.commerce.domain.models did not exist
```

### Case and Action contracts

```text
collection error
reason: ActionRiskLevel and Case models did not exist
```

### Evaluation contracts

```text
collection error
reason: app.commerce.domain.evaluation did not exist
```

### Gold Case fixtures

```text
collection error
reason: app.commerce.data.gold_cases did not exist
```

## Frozen real-data evidence

### GC-FULFILLMENT-001

Seller:

```text
4869f7a5dfa277a7dca6462dcf3b52b2
```

Selection:

- delivered orders only;
- single-seller orders only;
- purchase timestamps from `2017-12-02` inclusive to `2018-06-01` exclusive.

Metrics:

| Window | Orders | Late rate | Avg review | Handling hours | Transit hours |
|---|---:|---:|---:|---:|---:|
| Baseline: 2017-12-02 → 2018-01-31 | 141 | 3.5461% | 4.2286 | 50.06 | 300.51 |
| Anomaly: 2018-01-31 → 2018-04-01 | 202 | 35.1485% | 3.5980 | 46.84 | 494.83 |
| Recovery: 2018-04-01 → 2018-06-01 | 211 | 5.2133% | 4.2810 | 63.96 | 247.04 |

The anomaly does not support blaming seller handling: handling time improved while carrier transit time worsened substantially. The later recovery is observational and cannot prove an Action caused improvement, so follow-up remains `inconclusive`.

### GC-REVIEW-002

Seller:

```text
0b90b6df587eb83608a64ea8b390cf07
```

| Window | Orders | Late rate | Avg review | Low-rating rate |
|---|---:|---:|---:|---:|
| Baseline: 2018-03-01 → 2018-04-01 | 17 | 0% | 3.8824 | 23.5294% |
| Anomaly: 2018-04-01 → 2018-05-01 | 18 | 0% | 2.9444 | 44.4444% |

Review text contains allegations and reports consistent with suspected non-original goods, wrong/missing items and incomplete orders. The fixture forbids turning those allegations into a confirmed counterfeit, fraud or illegal-conduct finding.

### GC-CAPABILITY-003

This case is byte-for-byte identical to `GC-FULFILLMENT-001` for all non-review input tables. `order_reviews.csv` is absent.

Expected behavior:

- fulfillment diagnosis remains available;
- review experience capability becomes unavailable;
- `ReviewExperiencePathAgent` is skipped;
- review-score decline cannot be claimed;
- the missing review fields must be reported explicitly.

## GREEN verification

Command:

```text
cd backend
PYTHONPATH=. uv run pytest \
  tests/commerce/fixtures/test_gold_cases.py \
  tests/commerce/domain \
  tests/commerce/test_package_boundary.py \
  tests/test_harness_boundary.py -v
```

Result:

```text
61 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static check:

```text
PYTHONPATH=. uv run ruff check \
  app/commerce \
  tests/commerce \
  ../scripts/commerce_data/build_olist_gold_cases.py

All checks passed
exit code: 0
```

## Known limits

- The fixtures contain only one target seller each, so `SellerPeerPathAgent` is intentionally unavailable in these three cases.
- Public Olist data lacks exposure, click, add-to-cart, ad spend, inventory and profit.
- Review comments are order-level and user-generated; single-seller filtering reduces attribution ambiguity but does not establish legal truth.
- No model identity preflight or Agent test exists yet.
- Full raw Olist data remains outside Git under `/tmp/olist-kaggle`.

## Next

Phase 2 implements generic data intake, profiling, semantic mapping, Capability Registry, normalized facts, Metric Registry and anomaly detection on top of these frozen contracts.
