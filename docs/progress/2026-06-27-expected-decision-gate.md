# 2026-06-27 - OpenSKU Expected Decision Gate

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: add a deterministic decision-correctness gate so OpenSKU does not pass only because runtime and artifacts are valid.
- Scope: scorer tests, scorer implementation, CLI flag, real-run validation, docs, and regression.

## Thinking

The previous cross-stage run proved the live execution chain:

```text
real runtime -> all five specialists -> artifact writer -> validator -> present_files -> score_benchmark live-run PASS
```

But the run also exposed a sharper question: did the agent choose the benchmark-expected decision?

For `opensku-prelaunch-002`, the benchmark expected decision is `Pivot`, while the live run chose `Kill`. The existing scorer reported `PASS 60/60` because it validated execution integrity, not semantic decision agreement.

This milestone adds a separate optional gate:

```text
--decision-gate
```

It is intentionally optional so historical execution-integrity reports remain stable. Release-candidate validation should enable it.

## Acceptance Standard

This milestone is accepted only when all are true:

- Failing tests are added before implementation for matching, mismatched, and unresolved expected-decision cases.
- `score_expected_decision` resolves benchmark case files from live run evidence or run directory names.
- The scorer reads final decision from `launch-state.json`, with final-response fallback.
- `score_benchmark.py --decision-gate` adds an `expected-decision` result per live run.
- The real prelaunch injected run fails the new gate with `expected=Pivot` and `actual=Kill`.
- Existing live-run execution scoring remains separate and still passes for the same run.
- Regression tests and formatting checks pass.

## Actions Executed

| Action | Command / File | Result |
|---|---|---|
| Added red scoring tests | `backend/tests/test_opensku_scoring.py` | Initially failed because `score_expected_decision` did not exist |
| Implemented expected-decision scorer | `evals/opensku/scoring.py` | Added case inference, launch-state decision extraction, decision normalization, and `ScoreResult` checks |
| Added CLI gate | `evals/opensku/scoring.py` / `evals/opensku/score_benchmark.py` | `--decision-gate` appends expected-decision scoring for each `--live-run` |
| Ran scoring tests | `cd backend && uv run pytest tests/test_opensku_scoring.py -q` | `8 passed, 1 warning` |
| Ran real decision-gate report | `uv run --project backend python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --live-run docs/progress/runs/2026-06-27/live-knowledge-injection-prelaunch-002 --decision-gate --report-name 2026-06-27-phase-11-expected-decision-gate-prelaunch-002` | Expected failure: `status=FAIL`, `score=65/70` |
| Updated docs | `evals/opensku/README.md`, `docs/plans/opensku-complete-execution-plan.md` | Documented `--decision-gate` usage and release-candidate acceptance standard |
| Ran focused scoring regression | `cd backend && uv run pytest tests/test_opensku_scoring.py -q` | `8 passed, 1 warning` |
| Ran broader OpenSKU backend/eval regression | `cd backend && uv run pytest tests/test_opensku_live_batch.py tests/test_opensku_scoring.py tests/test_opensku_live_runner.py tests/test_opensku_cases.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_artifact_validators.py tests/test_opensku_benchmark_tool_policy.py tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q` | `80 passed, 1 warning` |
| Ran compile and diff checks | `uv run --project backend python -m py_compile evals/opensku/scoring.py evals/opensku/score_benchmark.py`; `git diff --check` | PASS |

## Evidence

Decision-gate report:

```text
evals/opensku/reports/2026-06-27-phase-11-expected-decision-gate-prelaunch-002/
├── failures.md
├── scores.json
└── summary.md
```

Report summary:

```text
Status: FAIL
Score: 65/70

case-suite         PASS 20/20
live-run           PASS 40/40
expected-decision  FAIL 5/10
```

Failure detail:

```text
expected=Pivot
actual=Kill
```

The case was resolved correctly:

```text
case_path=evals/opensku/cases/opensku-prelaunch-002.json
case_candidates=['opensku-prelaunch-002']
```

## Decision

Expected Decision Gate is accepted at implementation level.

The gate is doing the right thing: it preserves the existing execution-integrity score while exposing that the semantic decision does not match the benchmark expected decision.

## Validation

```text
focused_scoring=8 passed, 1 warning
broader_opensku=80 passed, 1 warning
py_compile=PASS
git diff --check=PASS
```

## Next

1. Done in `docs/progress/2026-06-27-prelaunch-decision-taxonomy.md`: hardened the `pre_launch_test` decision taxonomy so query/product mismatch yields `Pivot` when the SKU can be repositioned, and `Kill` only when the product itself should be abandoned.
2. Done: reran `opensku-prelaunch-002` as `live-decision-taxonomy-prelaunch-002` with the real live agent path.
3. Done: `evals/opensku/reports/2026-06-27-phase-12-prelaunch-taxonomy-decision-gate/` passed with `expected=Pivot`, `actual=Pivot`, `score=70/70`.
4. Remaining: add a release-candidate command that runs live-run scoring plus `--decision-gate` for a selected multi-run acceptance set.
