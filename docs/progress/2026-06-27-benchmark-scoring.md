# 2026-06-27 - OpenSKU-Bench Scoring Harness

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: execute the next evaluation milestone after live agent contract hardening.
- Scope: scoring module, CLI report generation, positive/negative reports, tests, and docs.

## Thinking

Phase 4 proved one live benchmark-fixture run can go through the real gateway/model/subagent/tool path and produce validator-clean artifacts. The next gap was benchmark scoring: OpenSKU had cases and validators, but it did not yet have a report that combines case-suite coverage, artifact-bundle validity, and live-run evidence into an inspectable score.

The scoring harness intentionally does not score revenue uplift, GMV, CTR, CVR, ROI, ad efficiency, or other private metrics. Those values are unavailable unless uploaded as real merchant data. Instead, the harness scores evidence that can be audited locally:

- whether the 30 benchmark cases cover the intended stages and traps
- whether an artifact bundle passes machine validation
- whether a live run actually invoked the runtime agent path, subagents, writer tool, validator, and `present_files`
- whether the final Chinese response covers the required user-facing fields and does not contradict generated artifact counts

Alternative rejected:

- Do not use an LLM judge as the first scoring layer. LLM judges may be useful later, but the foundation should be deterministic and reproducible.
- Do not make the score depend on fake business outcomes.
- Do not call a run "passed" just because artifacts exist; the tool trace and final response must also pass.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Added red tests for scoring API | `backend/tests/test_opensku_scoring.py` | Failed first because `evals.opensku.scoring` did not exist |
| 2026-06-27 | Implemented scoring core | `evals/opensku/scoring.py` | Scores case suite, artifact bundle, live-run evidence, and writes reports |
| 2026-06-27 | Added CLI wrapper | `evals/opensku/score_benchmark.py` | Fixed `sys.path` so it runs from repo root |
| 2026-06-27 | Added scoring docs | `evals/opensku/README.md` | Documents scoring layers, commands, and report paths |
| 2026-06-27 | Generated PASS report | `uv run python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --artifact-bundle evals/opensku/fixtures/golden/golden-001 --live-run docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001-bundle-writer-final-check --report-name 2026-06-27-phase-5-scoring-smoke` | `status=PASS`, `score=100/100` |
| 2026-06-27 | Generated negative-control report | `uv run python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --artifact-bundle evals/opensku/fixtures/broken/broken-003 --report-name 2026-06-27-phase-5-scoring-broken-check` | Expected failure: `status=FAIL`, `score=30/60` |

## Evidence

PASS report:

```text
evals/opensku/reports/2026-06-27-phase-5-scoring-smoke/summary.md
evals/opensku/reports/2026-06-27-phase-5-scoring-smoke/scores.json
evals/opensku/reports/2026-06-27-phase-5-scoring-smoke/failures.md
```

PASS report summary:

```text
Status: PASS
Score: 100/100
case-suite: 20/20
artifact-bundle: 40/40
live-run: 40/40
```

Negative-control report:

```text
evals/opensku/reports/2026-06-27-phase-5-scoring-broken-check/summary.md
evals/opensku/reports/2026-06-27-phase-5-scoring-broken-check/scores.json
evals/opensku/reports/2026-06-27-phase-5-scoring-broken-check/failures.md
```

Negative-control failure caught:

```text
evidence-ledger.json: evidence item 1 treats private metric 'gmv' as observed_public; private metric must be uploaded_real or unavailable
```

## Validation

Scoring unit tests:

```bash
cd backend
uv run pytest tests/test_opensku_scoring.py -q
```

Result:

```text
5 passed, 1 warning
```

Final related regression:

```bash
cd backend
uv run pytest tests/test_opensku_scoring.py tests/test_opensku_cases.py tests/test_opensku_artifact_validators.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_live_runner.py tests/test_opensku_benchmark_tool_policy.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q
uv run python -m py_compile ../evals/opensku/scoring.py ../evals/opensku/score_benchmark.py ../evals/opensku/run_live_agent_validation.py
```

Result:

```text
54 passed, 1 warning
```

What the tests cover:

- generated 30-case suite scores `20/20`
- golden artifact bundle scores `40/40`
- broken private-metric fixture fails
- complete live-run evidence scores `40/40`
- live-run evidence missing `write_opensku_artifact_bundle` fails
- report writer creates `summary.md`, `scores.json`, and `failures.md`

What was not tested yet:

- batch live-run scoring across all 30 cases
- LLM-as-judge qualitative scoring
- UI surfacing of score reports

Those should be later layers on top of this deterministic scoring base.

## Decision

Phase 5 scoring harness is accepted as a deterministic benchmark-report layer.

## Next

1. Add batch live-run orchestration for selected benchmark cases.
2. Surface score reports in the OpenSKU UI or demo docs.
3. Decide whether to add a separate LLM judge after deterministic checks are stable.
