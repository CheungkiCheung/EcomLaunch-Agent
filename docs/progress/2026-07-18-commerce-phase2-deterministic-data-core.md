# Commerce Case Agent Phase 2 — Deterministic Data Core

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: deterministic core complete; real-model semantic candidate layer pending
> Model requests: `0`

## Outcome

The Commerce data path now processes heterogeneous inputs into traceable capabilities, normalized facts, metrics and anomaly signals without using an LLM.

Implemented:

- fail-closed CSV, JSON, JSONL, Excel and ZIP intake;
- immutable raw-file storage with SHA-256, encoding, size and table manifests;
- ZIP traversal, symbolic-link, duplicate-member, size and compression-ratio protection;
- deterministic schema and quality profiler;
- missing rate, unique rate, primary-key candidates, time candidates, numeric ranges and duplicate rows;
- leading-zero preservation and one-to-many / many-to-many Join risk detection;
- deterministic Olist semantic rules;
- low-confidence mappings that remain unconfirmed;
- file-backed Workspace user confirmations;
- Capability Registry with required/optional semantics, dependencies and diversity gates;
- `available / partial / unavailable` plus machine-readable reason codes;
- Olist-specific normalized entity/fact adapter;
- stable Entity and Fact IDs, raw source locators and semantic versions;
- versioned Metric Registry and seller-window metric engine;
- explicit unknown metrics when Review data is missing;
- metric-specific anomaly thresholds, minimum samples, severity and confidence;
- deterministic anomaly deduplication and Case candidate merge.

No LLM or Agent behavior was tested. A DeepSeek V4 candidate provider has not been wired into Semantic Mapper yet.

## Safety and evidence boundaries

### Intake

- Raw input copies are read-only.
- ZIP members are never extracted with unsafe path helpers.
- Absolute paths, `..`, Windows-style separators and archive symbolic links are rejected.
- Unsupported archive members are reported as warnings.
- Nested ZIP files are ignored rather than recursively expanded.
- The manifest records file identity independently from table identity.

### Profiling

- Values are inspected without modifying source files.
- Strings with leading zeros remain strings.
- Mixed columns are not coerced into numeric types.
- Join cardinality warns when naive joins can multiply rows.

### Semantic mapping

- Exact deterministic rules can auto-confirm.
- Ambiguous aliases remain `needs_confirmation`.
- User confirmations persist at Workspace scope.
- No fake LLM or stub candidate provider is used.
- Future DeepSeek V4 suggestions will be candidates only and require the real-model preflight.

### Metrics

- Metrics are computed from normalized Facts, not from Agent prose.
- Known metrics record Formula Version, window, sample size, numerator/denominator and Source Fact IDs.
- Missing Review capability yields `unknown`, not zero.
- Metric and anomaly IDs are deterministic for the same dataset, seller, metric and window.

### Anomalies

- Direction and thresholds are metric-specific.
- Improved seller handling does not become an adverse signal.
- Review-only degradation does not create a delivery-lateness signal.
- Small samples are capped at low severity and confidence at or below `0.4`.
- Repeated signals for the same seller/window merge into one deterministic Case candidate.

## RED evidence

Each group first failed because the target module was absent:

```text
app.commerce.data.intake
app.commerce.data.profiler
app.commerce.data.semantic_mapper
app.commerce.data.capabilities
app.commerce.data.normalized
app.commerce.metrics.registry
app.commerce.metrics.anomaly
```

No failing assertion was weakened to reach GREEN.

## GREEN verification

Command:

```text
cd backend
PYTHONPATH=. uv run pytest \
  tests/commerce \
  tests/test_harness_boundary.py \
  tests/test_commerce_feature_flag.py -q
```

Result:

```text
100 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static verification:

```text
PYTHONPATH=. uv run ruff check \
  app/commerce \
  tests/commerce \
  ../scripts/commerce_data/build_olist_gold_cases.py \
  app/gateway/config.py \
  tests/test_commerce_feature_flag.py

All checks passed
exit code: 0
```

## Remaining Phase 2 work

- wire a DeepSeek V4 semantic-candidate adapter only after `real_model_preflight` exists;
- run its tests with fresh real requests, never mocks or replay;
- add a reproducible multi-seller peer cohort and execute peer-baseline metrics;
- execute geographic-segment metrics rather than only registering their formulas;
- persist Dataset Profile, Semantic Mapping, Capability Profile and Normalized Facts through the Phase 3 repositories;
- expose data-quality and capability reports through the future API and Domain Event stream.

## Next

The next deterministic work can start Phase 3 persistence and Domain Events while the real-model preflight is designed in parallel. Formal Agent routing remains blocked until the DeepSeek V4 gate is verifiable.
