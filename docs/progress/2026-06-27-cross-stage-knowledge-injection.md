# 2026-06-27 - OpenSKU Cross-Stage Knowledge Injection

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: verify knowledge reuse injection outside `idea_only` with a real live run.
- Scope: selector hardening, cross-stage live validation, scoring, knowledge quality, and progress evidence.

## Thinking

The previous accepted knowledge-injected run used `idea_only`. That proves reuse works, but it does not prove the selector is safe across launch stages.

The next useful validation is a non-idea case, preferably `pre_launch_test`, because it checks search-fit behavior and avoids turning public query fixtures into private commerce metrics.

Before spending a real live call, I checked selected patterns for several non-idea cases. That surfaced a selector risk:

```text
kp_0002 statement: Current loop state is Hold at stage pre_launch_test.
source_case_ids includes: batch-live-stage2-opensku-softlaunch-002
current stage_matches included: pre_launch_test and soft_launch
```

For decision patterns, the statement's stage must be treated as the decision's own stage. A source run id can describe where the pattern came from, but it must not widen a decision rule into another launch stage.

During the knowledge promotion pass, a second risk surfaced: `kp_XXXX` pattern IDs are generated from current aggregate order, so they can drift after new deltas are ingested. Promotion now uses stable `reuse_key` matching before falling back to ID. For decision patterns, promotion also requires the final `launch-state.json` decision to match the decision in the pattern statement.

## Acceptance Standard

This milestone is accepted only when all are true:

- A failing regression test captures the inconsistent-stage decision pattern case.
- Selector no longer injects a decision pattern into `soft_launch` when its statement says `pre_launch_test`.
- `pre_launch_test` selection still includes only globally safe patterns and `pre_launch_test` decision patterns.
- One real `pre_launch_test` live run executes with `--knowledge-dir docs/knowledge/opensku`.
- The live run passes artifact validation and independent scoring.
- The live run manifest records `injected_knowledge_patterns`.
- Pattern promotion matches by stable reuse key, not only generated pattern ID.
- Decision-pattern promotion requires final decision match.
- Knowledge ingest, promotion, and quality scoring still pass after the new run.
- Logs record commands, evidence, results, and residual risks.

## Actions Executed

| Action | Command / File | Result |
|---|---|---|
| Started cross-stage validation | Case candidates under `evals/opensku/cases/` | Chose `pre_launch_test` as the next validation stage |
| Prechecked selected patterns | Local selector check over prelaunch, softlaunch, scale cases | Found inconsistent decision stage inference risk in `kp_0002` |
| Added red regression test | `backend/tests/test_opensku_knowledge_context.py::test_decision_statement_stage_is_not_widened_by_source_case_id` | Initially failed because `kp_bug` inferred both `pre_launch_test` and `soft_launch` |
| Tightened stage inference | `evals/opensku/knowledge_context.py` | Decision pattern statement/reuse-key stage now wins over source case id stage inference |
| Ran focused selector test | `cd backend && uv run pytest tests/test_opensku_knowledge_context.py -q` | `3 passed, 1 warning` |
| Rechecked selected patterns | Local selector check for `opensku-prelaunch-002`, `opensku-softlaunch-002`, and `opensku-scale-003` | `soft_launch` no longer receives the `kp_0002` prelaunch decision pattern |
| Ran real prelaunch injected live validation | `uv run --project backend python evals/opensku/run_live_agent_validation.py --case-id live-knowledge-injection-prelaunch-002 --case-file evals/opensku/cases/opensku-prelaunch-002.json --date 2026-06-27 --timeout-seconds 900 --reasoning-effort medium --knowledge-dir docs/knowledge/opensku` | `LIVE_VALIDATION_PASSED` |
| Scored prelaunch live run | `uv run --project backend python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --live-run docs/progress/runs/2026-06-27/live-knowledge-injection-prelaunch-002 --report-name 2026-06-27-phase-10-cross-stage-knowledge-injection-score` | `status=PASS`, `score=60/60` |
| Rebuilt knowledge base | `uv run --project backend python scripts/opensku/ingest_knowledge_deltas.py --runs docs/progress/runs --output docs/knowledge/opensku --min-records 20` | `status=PASS`, `accepted_run_count=16`, `record_count=48`, `pattern_count=10` |
| Added red promotion ID-drift test | `backend/tests/test_opensku_knowledge_promotion.py::test_promote_knowledge_maturity_matches_reuse_key_when_pattern_ids_drift` | Initially failed because promotion matched by drifting `kp_XXXX` ID |
| Fixed promotion stable matching | `scripts/opensku/promote_knowledge_maturity.py` | Promotion now matches injected evidence by `reuse_key` before ID fallback |
| Added red decision-match promotion test | `backend/tests/test_opensku_knowledge_promotion.py::test_promote_decision_pattern_requires_matching_final_decision` | Initially failed because a successful run promoted both Hold and Pivot decision patterns |
| Fixed decision promotion gate | `scripts/opensku/promote_knowledge_maturity.py` | Decision promotion now requires final `launch-state.json` decision to match pattern statement |
| Ran focused promotion/selector tests | `cd backend && uv run pytest tests/test_opensku_knowledge_promotion.py tests/test_opensku_knowledge_context.py -q` | `7 passed, 1 warning` |
| Re-ran ingest, promotion, quality gates | `ingest_knowledge_deltas.py && promote_knowledge_maturity.py && knowledge_delta_quality.py` | `status=PASS`; `verified_reuse_pattern_count=3`; quality `score=60/60` |
| Ran focused OpenSKU regression | `cd backend && uv run pytest tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py tests/test_opensku_live_runner.py tests/test_opensku_live_batch.py -q` | `27 passed, 1 warning` |
| Ran broader OpenSKU backend/eval regression | `cd backend && uv run pytest tests/test_opensku_live_batch.py tests/test_opensku_scoring.py tests/test_opensku_live_runner.py tests/test_opensku_cases.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_artifact_validators.py tests/test_opensku_benchmark_tool_policy.py tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q` | `77 passed, 1 warning` |
| Ran compile and diff checks | `uv run --project backend python -m py_compile ...`; `git diff --check` | PASS |

## Evidence

Real live run:

```text
docs/progress/runs/2026-06-27/live-knowledge-injection-prelaunch-002/
├── artifacts-manifest.json
├── final-response.md
├── notes.md
├── raw-run-events.json
├── run-log.md
└── validator-output.txt
```

Score report:

```text
evals/opensku/reports/2026-06-27-phase-10-cross-stage-knowledge-injection-score/
├── failures.md
├── scores.json
└── summary.md
```

Runtime result:

```text
run_id=9bdf284d-addd-4e31-abae-319ffe3f1c35
run_status=success
present_files_called=True
artifact_writer_called=True
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
external_search_tool_calls=[]
artifact_count=10
validator status=PASS
LIVE_VALIDATION_PASSED
```

Injected patterns at runtime:

```text
kp_0008 pitfall  -> private metric boundary
kp_0009 process  -> runtime artifact writer plus validator
kp_0006 decision -> pre_launch_test Pivot pattern
kp_0002 decision -> pre_launch_test Hold pattern
```

These are snapshot-local IDs from the knowledge state before the new run was ingested. After ingest, IDs changed. Promotion therefore uses `reuse_key` and final decision matching.

Final run decision:

```text
stage=pre_launch_test
decision=Kill
```

Knowledge base after the run:

```text
status=PASS
accepted_run_count=16
record_count=48
pattern_count=10
```

Promotion after strict gates:

```text
status=PASS
scanned_run_count=23
reuse_evidence_count=12
promoted_count=3
verified_reuse_pattern_count=3
```

Verified reused patterns after strict promotion:

```text
kp_0001 decision -> Current loop state is Hold at stage idea_only.
kp_0009 pitfall  -> Do not convert public fixtures or public review language into private commerce metrics.
kp_0010 process  -> Use a runtime artifact writer plus validator for benchmark runs.
```

The prelaunch Hold/Pivot decision patterns were not verified by this run because the final decision was `Kill`. This is intentional: a successful run can prove a boundary/process pattern was useful, but it cannot verify a decision pattern that the final evidence did not support.

Knowledge quality:

```text
status=PASS
score=60/60
record_count=48
reused_pattern_count=5
pattern_count=10
```

Regression:

```text
focused=27 passed, 1 warning
broader_opensku=77 passed, 1 warning
py_compile=PASS
git diff --check=PASS
```

## Decision

Cross-stage knowledge injection is accepted at implementation level:

- selector no longer widens decision patterns across stages via source case ids.
- a real `pre_launch_test` live run used injected knowledge and passed validator/scoring.
- promotion no longer trusts drifting `kp_XXXX` IDs.
- decision promotion now requires final decision match.
- knowledge ingest, promotion, and quality gates pass after the new run.

## Next

1. Surface injected knowledge IDs/statements/maturity in the UI or demo report.
2. Add a release-candidate command that runs ingest -> promotion -> quality -> selected live score.
3. Consider adding expected-decision scoring as a separate scorer; current `score_benchmark.py` verifies execution/artifact integrity, not semantic agreement with the hidden benchmark decision.
