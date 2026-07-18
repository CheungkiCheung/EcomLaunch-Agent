# Commerce Case Agent Phase 2 — Peer Cohort and Geographic Metrics

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: deterministic peer and geographic paths complete
> Model requests: `0`

## Outcome

`SellerPeerPathAgent` now has a real, reproducible multi-seller data contract instead of only a registered formula. The metric layer can build an outcome-agnostic cohort, compute target and pooled peer late-delivery rates, preserve stable IDs and source Fact lineage, and group a seller's distinct orders by customer state.

Implemented:

- `CohortId` and immutable peer/geographic metric contracts;
- `PeerCohortPolicy@1.0.0`;
- same time-window, pure-category and seller-state matching;
- mandatory single-seller attribution;
- minimum eligible order threshold per seller;
- peer eligibility independent from the late/not-late result value;
- target and pooled peer `MetricObservation` objects;
- deterministic Cohort and dimension-aware Metric Observation IDs;
- explicit `PeerCohortUnavailableError` when the target or peers fail eligibility;
- customer-state `geographic_order_count` execution;
- `unknown` geographic output when customer-state data cannot be joined;
- source Fact IDs for cohort selection, rate calculation and geographic segments;
- `GC-PEER-004`, built from the frozen real Olist source files.

## Frozen cohort

Selection:

```text
purchase window: 2018-01-01 inclusive → 2018-07-01 exclusive
product category: fashion_bolsas_e_acessorios
seller state: SP
single-seller orders only: true
pure-category orders only: true
minimum orders per seller: 20
eligible sellers: 6
```

Target seller:

```text
e5a3438891c0bfdb9394643f95273d8e
orders: 59
late orders: 16
late-delivery rate: 27.1186%
```

Five pooled peers:

```text
orders: 257
late orders: 19
late-delivery rate: 7.3930%
target minus peer gap: 19.7256 percentage points
```

Target customer-state counts start with:

```text
SP: 26
MG: 8
RJ: 7
```

The rate gap is a diagnostic signal, not a causal finding. Cohort membership uses visible matching dimensions and sample sufficiency, but it does not control every carrier, route, customer or product characteristic. `GC-PEER-004` therefore machine-blocks claims that the peer gap proves seller-controlled causation or that an unobserved Action improved the seller.

## Fixture size

```text
orders: 316
order_items: 331
order_reviews: 317
products: 135
customers: 316
sellers: 6
total committed fixture size: approximately 189 KB
```

The full Olist source remains outside Git.

## TDD evidence

The first focused run failed during collection because `PeerCohortPolicy` did not exist:

```text
ImportError: cannot import name 'PeerCohortPolicy'
exit code: 2
```

The implementation then added the minimum contracts and deterministic engines without weakening existing Metric or Gold Case assertions.

## Focused verification

```text
cd backend
.venv/bin/pytest -q \
  tests/commerce/metrics/test_registry.py \
  tests/commerce/data/test_capabilities.py \
  tests/commerce/fixtures/test_gold_cases.py

31 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static verification:

```text
.venv/bin/ruff check \
  app/commerce/domain \
  app/commerce/data/capabilities.py \
  app/commerce/metrics \
  ../scripts/commerce_data/build_olist_gold_cases.py \
  tests/commerce/metrics/test_registry.py \
  tests/commerce/data/test_capabilities.py \
  tests/commerce/fixtures/test_gold_cases.py

All checks passed
exit code: 0
```

Full Commerce deterministic regression, with the live real-model test explicitly separated:

```text
cd backend
.venv/bin/pytest -q tests/commerce \
  --ignore=tests/commerce/evaluation/test_real_model_preflight_live.py \
  tests/test_commerce_feature_flag.py

140 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

## Remaining boundary

This stage does not implement `SellerPeerPathAgent`. It only makes the underlying Capability, Cohort, Metric and Gold Case deterministic and auditable. Any future Agent test over this fixture must pass the real DeepSeek V4 preflight and issue a fresh provider request.

## Next

Phase 2's major deterministic metric gaps are now closed. The next independent work is Phase 3 persistence and Domain Events: repositories, optimistic concurrency, event sequencing, API contracts and the feature-flagged Commerce router.
