# 2026-06-27 - Phase 2 Benchmark Case Schema

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: `c85a39b`
- Goal: execute Phase 2 from `docs/plans/opensku-complete-execution-plan.md`.
- Scope: OpenSKU-Bench case schema, 30 benchmark cases, validator, matrix printer, and validation log.

## Thinking

Phase 2 turns the open-data strategy into a real evaluation surface. A project that only has "generate a launch pack" is easy to dismiss. A project with 30 stage-balanced benchmark cases, explicit evidence references, forbidden-claim traps, and validation commands has a stronger agent-engineering story.

The main design choice was to generate cases from Phase 1's real sampled rows instead of hand-writing disconnected mock cases. That keeps benchmark cases tied to actual public fixture files while still making them deterministic and easy to regenerate.

Alternatives rejected:

- Do not build a benchmark only around one seven-day launch scenario.
- Do not make every case a happy path.
- Do not count public datasets as uploaded merchant telemetry. Uploaded-data simulation uses public fixture rows and labels them as `public_fixture_as_uploaded_simulation`.
- Do not rely on prose review alone. A machine validator checks counts, tags, source references, decisions, rationale, and referenced sample files.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Read Phase 2 requirements | `sed -n '390,470p' docs/plans/opensku-complete-execution-plan.md` | Confirmed schema fields, 30-case target, acceptance criteria, and validation commands. |
| 2026-06-27 | Added TDD test for case validator | `backend/tests/test_opensku_cases.py` | First run failed because `evals.opensku.validate_cases` did not exist. |
| 2026-06-27 | Added schema and docs | `evals/opensku/case_schema.json`; `evals/opensku/README.md`; `evals/opensku/fixtures/README.md` | Defines required case fields and benchmark boundary. |
| 2026-06-27 | Added deterministic case generator | `evals/opensku/build_cases_from_samples.py` | Reads `data/opensku/samples/*.jsonl` and generates cases from real sampled rows. |
| 2026-06-27 | Added validator | `evals/opensku/validate_cases.py` | Validates required fields, source refs, stage counts, suite size, tag thresholds, and loop artifacts. |
| 2026-06-27 | Added matrix printer | `evals/opensku/print_case_matrix.py` | Prints a compact stage/case/decision/source/tag matrix. |
| 2026-06-27 | Generated 30 cases | `uv run python evals/opensku/build_cases_from_samples.py` | Passed: wrote 30 files under `evals/opensku/cases/`. |
| 2026-06-27 | Ran case unit tests | `cd backend && uv run pytest tests/test_opensku_cases.py -q` | Passed: `2 passed, 1 warning in 0.14s`. |
| 2026-06-27 | Ran required validator | `uv run python evals/opensku/validate_cases.py` | Passed: `VALIDATION PASSED`. |
| 2026-06-27 | Ran required matrix printer | `uv run python evals/opensku/print_case_matrix.py` | Passed: printed all 30 cases and `total_cases=30`. |

## Evidence

### Deliverables

```text
evals/__init__.py
evals/opensku/__init__.py
evals/opensku/case_schema.json
evals/opensku/README.md
evals/opensku/fixtures/README.md
evals/opensku/build_cases_from_samples.py
evals/opensku/validate_cases.py
evals/opensku/print_case_matrix.py
evals/opensku/cases/*.json
backend/tests/test_opensku_cases.py
```

### Generator Output

Command:

```bash
uv run python evals/opensku/build_cases_from_samples.py
```

Output:

```text
wrote_cases=30
cases_dir=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/evals/opensku/cases
```

### Validator Output

Command:

```bash
uv run python evals/opensku/validate_cases.py
```

Output:

```text
case_count=30
stage_counts={'idea_only': 6, 'supplier_sample': 6, 'pre_launch_test': 6, 'soft_launch': 8, 'scale_iterate': 4}
tag_counts={'public_signal_context': 16, 'stage_diagnosis': 30, 'forbidden_metric_trap': 20, 'unsupported_claim_trap': 8, 'promotion_replan': 12, 'knowledge_delta': 12, 'uploaded_data_simulation': 14}
VALIDATION PASSED
```

### Matrix Output Summary

Command:

```bash
uv run python evals/opensku/print_case_matrix.py
```

Summary:

```text
total_cases=30
```

Stage coverage:

```text
idea_only: 6
supplier_sample: 6
pre_launch_test: 6
soft_launch: 8
scale_iterate: 4
```

Representative cases:

```text
opensku-idea-001 -> Hold -> amazon_reviews, wands
opensku-supplier-004 -> Go -> amazon_reviews, wands
opensku-prelaunch-001 -> Go -> wands
opensku-softlaunch-003 -> Scale -> olist
opensku-scale-001 -> Scale -> olist, wands
```

### Test Output

Command:

```bash
cd backend && uv run pytest tests/test_opensku_cases.py -q
```

Output:

```text
..                                                                       [100%]
2 passed, 1 warning in 0.14s
```

Warning:

```text
LangChainPendingDeprecationWarning from langgraph.checkpoint.serde.encrypted
```

Assessment: external deprecation warning, not a Phase 2 blocker.

## Validation

Phase 2 acceptance criteria:

| Requirement | Evidence | Status |
|---|---|---|
| `evals/opensku/case_schema.json` validates all cases | `validate_cases.py` checks required fields and source references for all cases | Passed |
| every case has source dataset and stage | Validator enforces non-empty `source_dataset` and valid stage enum | Passed |
| every case has expected decision with rationale | Validator requires `expected_decision` enum and non-empty `expected_decision_rationale` | Passed |
| no case relies on invented live backend data | Cases only use `public_benchmark_fixture` or `public_fixture_as_uploaded_simulation` source types | Passed |
| at least 10 cases include uploaded-data simulation | `uploaded_data_simulation`: 14 | Passed |
| at least 10 cases include public-signal context | `public_signal_context`: 16 | Passed |
| at least 5 cases catch forbidden metric hallucination | `forbidden_metric_trap`: 20 | Passed |
| at least 5 cases catch unsupported product/spec/policy claims | `unsupported_claim_trap`: 8 | Passed |
| required validation commands pass | `uv run python evals/opensku/validate_cases.py`; `uv run python evals/opensku/print_case_matrix.py` | Passed |

What was not tested:

- No live agent run was executed in Phase 2.
- No artifact-output validation was executed yet.
- No LLM scoring harness was executed yet.

These are Phase 3 and later requirements.

## Decision

Phase 2 is complete.

Proceed to Phase 3: Artifact Schemas And Validators.

## Next

1. Define machine-checkable contracts for required OpenSKU artifacts.
2. Implement artifact validators for JSON, CSV, and Markdown outputs.
3. Add tests that prove invalid artifacts fail for missing fields, inconsistent evidence ids, forbidden private metrics, and unsupported claims.
4. Run Phase 3 validation commands and write the next progress log.

