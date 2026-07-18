# 2026-06-27 - OpenSKU Release-Candidate Decision Gate

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: add a reproducible release-candidate gate that scores selected real live-run evidence with the expected-decision gate enabled.
- Scope: RC config, RC gate runner, tests, first five-stage RC report, 10-run probe triage, docs.

## Thinking

The single-run expected-decision gate proved it can catch semantic mistakes, but release-candidate validation should not depend on a hand-written long `score_benchmark.py` command. A reviewer should be able to run one command against a named candidate set and get:

- candidate config validation
- benchmark case-suite validation
- live runtime evidence validation
- expected Go/Pivot/Hold/Kill/Scale decision validation per selected run

I first probed the current 10-run acceptance set with `--decision-gate`. That probe failed, which is useful and must stay visible:

```text
status=FAIL
score=500/520
```

The failing historical runs were:

```text
batch-live-5stage-opensku-prelaunch-001: expected=Go, actual=Pivot
batch-live-stage2-opensku-idea-002: expected=Pivot, actual=Hold
batch-live-stage2-opensku-supplier-002: expected=Pivot, actual=Hold
batch-live-stage2-opensku-softlaunch-002: expected=Pivot, actual=Hold
```

Those should not be hidden by choosing only passing runs. The first accepted RC gate is therefore explicitly a five-stage semantic RC gate, not the final 10-run release gate. It uses one passing real live run per stage, including the corrected `live-decision-taxonomy-prelaunch-002` run from the Pivot/Kill taxonomy fix.

## Acceptance Standard

This milestone is accepted only when all are true:

- A named release-candidate file declares selected real live-run evidence.
- The RC gate validates live-run count, required stage counts, run paths, case files, and duplicate case IDs.
- The RC gate scores the case suite.
- The RC gate scores every selected live run with runtime/artifact checks.
- The RC gate enables expected-decision checks by default.
- Tests cover config validation and automatic expected-decision scoring.
- At least one multi-stage RC report passes using existing real live-run evidence.
- The known 10-run decision-gate failures are documented as next work.

## Actions Executed

| Action | Command / File | Result |
|---|---|---|
| Probed current 10-run set | `uv run --project backend python evals/opensku/score_benchmark.py ... --decision-gate --report-name 2026-06-27-rc-gate-probe` | Expected FAIL: `score=500/520`; four semantic mismatches found |
| Added failing tests | `backend/tests/test_opensku_release_candidate_gate.py` | Red: `ModuleNotFoundError: No module named 'evals.opensku.release_candidate_gate'` |
| Implemented RC gate module | `evals/opensku/release_candidate_gate.py` | Adds config loading, config scoring, live-run scoring, expected-decision scoring, and report writing |
| Added CLI wrapper | `evals/opensku/run_release_candidate_gate.py` | One-command RC gate entrypoint |
| Added named RC config | `evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json` | Five-stage selected live-run evidence set |
| Ran focused tests | `cd backend && uv run pytest tests/test_opensku_release_candidate_gate.py -q` | PASS: 2 passed, 1 warning |
| Ran five-stage RC gate | `uv run --project backend python evals/opensku/run_release_candidate_gate.py --candidate-file evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json --report-name 2026-06-27-rc1-five-stage-decision-gate` | PASS: `score=280/280` |
| Ran compile checks | `uv run --project backend python -m py_compile evals/opensku/release_candidate_gate.py evals/opensku/run_release_candidate_gate.py` | PASS |
| Ran focused scoring regression | `cd backend && uv run pytest tests/test_opensku_release_candidate_gate.py tests/test_opensku_scoring.py -q` | PASS: 10 passed, 1 warning |
| Ran broader OpenSKU regression | `cd backend && uv run pytest tests/test_opensku_live_batch.py tests/test_opensku_scoring.py tests/test_opensku_release_candidate_gate.py tests/test_opensku_live_runner.py tests/test_opensku_cases.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_artifact_validators.py tests/test_opensku_benchmark_tool_policy.py tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q` | PASS: 83 passed, 1 warning |
| Ran diff whitespace check | `git diff --check` | PASS |

## Evidence

RC candidate config:

```text
evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json
```

Passing RC report:

```text
evals/opensku/reports/2026-06-27-rc1-five-stage-decision-gate/
├── failures.md
├── scores.json
└── summary.md
```

Report summary:

```text
Status: PASS
Score: 280/280

release-candidate-config PASS 10/10
case-suite               PASS 20/20
5 live-run checks         PASS 40/40 each
5 expected-decision gates PASS 10/10 each
```

10-run probe report:

```text
evals/opensku/reports/2026-06-27-rc-gate-probe/
├── failures.md
├── scores.json
└── summary.md
```

## Validation

```text
focused_release_candidate_tests=2 passed, 1 warning
focused_release_candidate_and_scoring=10 passed, 1 warning
five_stage_rc_gate=PASS 280/280
ten_run_probe=FAIL 500/520, four decision mismatches intentionally recorded
broader_opensku_regression=83 passed, 1 warning
py_compile=PASS
git diff --check=PASS
```

## Decision

Accepted for the first multi-stage release-candidate decision gate.

This does not mark the full 10-run RC gate complete. The next semantic hardening loop should address the four 10-run mismatches through taxonomy fixes or real reruns, then create a 10-run RC config that passes with `--decision-gate`.

## Next

1. Add taxonomy guidance for Go/Pivot/Hold boundaries exposed by the 10-run probe.
2. Rerun the four mismatched cases through the real live agent path.
3. Create a `2026-06-27-rc2-10run.json` candidate only after those reruns pass expected-decision gates.
4. Fold the 10-run RC gate into final Phase 11 verification.
