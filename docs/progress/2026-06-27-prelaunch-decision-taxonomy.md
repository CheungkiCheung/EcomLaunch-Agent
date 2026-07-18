# 2026-06-27 - OpenSKU Prelaunch Decision Taxonomy

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: fix the `pre_launch_test` Pivot/Kill boundary exposed by the expected-decision gate.
- Scope: agent contract, live prompt taxonomy, tests, real rerun, decision-gate validation, and documentation.

## Thinking

The expected-decision gate correctly failed the real `opensku-prelaunch-002` run:

```text
expected=Pivot
actual=Kill
```

The run was not broken operationally. It passed runtime, subagents, artifact writing, validators, and final-response checks. The failure is semantic: in a pre-launch search-fit test, query/product/category mismatch usually means the targeting or positioning path is wrong, not necessarily that the SKU itself must be abandoned.

The decision boundary should be:

```text
Pivot = change target query, audience, channel, positioning, claim, or offer while the SKU may still be testable.
Kill = abandon the SKU or offer because evidence shows a non-salvageable product, supply, compliance, or economics failure.
```

For `pre_launch_test`, a severe query mismatch should be `Pivot` unless evidence proves the SKU itself has no viable retargeting path.

## Acceptance Standard

This milestone is accepted only when all are true:

- Failing contract tests are added before implementation.
- `agents/ecom-launch/SOUL.md`, `skills/custom/ecom-launch/SKILL.md`, and `docs/ecom-launch/manual-run-prompt.md` define the Pivot/Kill boundary.
- `evals/opensku/run_live_agent_validation.py` includes the same generic taxonomy in benchmark live prompts.
- Existing contract and live-runner tests pass.
- A real `opensku-prelaunch-002` knowledge-injected live run is executed.
- `score_benchmark.py --decision-gate` passes for the rerun.
- Logs and docs record the commands, evidence, and outcome.

## Actions Executed

| Action | Command / File | Result |
|---|---|---|
| Started taxonomy fix | This log | Done |
| Added failing contract tests | `backend/tests/test_ecom_launch_contract.py`, `backend/tests/test_opensku_live_runner.py` | Red test confirmed: missing Pivot/Kill boundary in skill, SOUL, manual prompt, and live prompt |
| Updated agent contract | `skills/custom/ecom-launch/SKILL.md`, `agents/ecom-launch/SOUL.md`, `docs/ecom-launch/manual-run-prompt.md` | Added Go/Pivot/Hold/Kill/Scale taxonomy and `pre_launch_test` search-fit Pivot default |
| Updated live benchmark prompt | `evals/opensku/run_live_agent_validation.py` | Added same decision taxonomy to case-based benchmark prompts |
| Focused contract regression | `cd backend && uv run pytest tests/test_ecom_launch_contract.py tests/test_opensku_live_runner.py -q` | PASS: 13 passed, 1 warning |
| Python compile check | `uv run --project backend python -m py_compile evals/opensku/run_live_agent_validation.py` | PASS |
| Real live rerun | `uv run --project backend python evals/opensku/run_live_agent_validation.py --case-id live-decision-taxonomy-prelaunch-002 --case-file evals/opensku/cases/opensku-prelaunch-002.json --date 2026-06-27 --timeout-seconds 900 --reasoning-effort medium --knowledge-dir docs/knowledge/opensku` | PASS: real DeepSeek run, all five ecommerce subagents, artifact writer, validator, and `present_files` |
| Expected-decision gate | `uv run --project backend python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --live-run docs/progress/runs/2026-06-27/live-decision-taxonomy-prelaunch-002 --decision-gate --report-name 2026-06-27-phase-12-prelaunch-taxonomy-decision-gate` | PASS: `score=70/70`, `expected=Pivot`, `actual=Pivot` |
| Knowledge ingest | `uv run --project backend python scripts/opensku/ingest_knowledge_deltas.py --runs docs/progress/runs --output docs/knowledge/opensku --min-records 20` | PASS: `accepted_run_count=17`, `record_count=51`, `pattern_count=10` |
| Knowledge maturity promotion | `uv run --project backend python scripts/opensku/promote_knowledge_maturity.py --knowledge docs/knowledge/opensku --runs docs/progress/runs --min-promotions 1` | PASS: `reuse_evidence_count=17`, `promoted_count=4`, `verified_reuse_pattern_count=4` |
| Knowledge quality gate | `uv run --project backend python evals/opensku/scorers/knowledge_delta_quality.py --knowledge docs/knowledge/opensku --min-records 20 --min-reused-patterns 5` | PASS: `score=60/60`, `reused_pattern_count=5` |
| OpenSKU regression | `cd backend && uv run pytest tests/test_opensku_live_batch.py tests/test_opensku_scoring.py tests/test_opensku_live_runner.py tests/test_opensku_cases.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_artifact_validators.py tests/test_opensku_benchmark_tool_policy.py tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q` | PASS: 81 passed, 1 warning |
| Diff whitespace check | `git diff --check` | PASS |

## Evidence

Live run:

```text
run_id=b31036d6-76c5-45d9-8e82-ad9bd73b4c4e
thread_id=opensku-live-live-decision-taxonomy-prelaunch-002-1782573088
run_dir=docs/progress/runs/2026-06-27/live-decision-taxonomy-prelaunch-002
model=deepseek/deepseek-v4-flash
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
artifact_writer_called=True
present_files_called=True
artifact_count=10
status=PASS
```

Decision-gate report:

```text
evals/opensku/reports/2026-06-27-phase-12-prelaunch-taxonomy-decision-gate/
├── failures.md
├── scores.json
└── summary.md
```

Report summary:

```text
Status: PASS
Score: 70/70

case-suite         PASS 20/20
live-run           PASS 40/40
expected-decision  PASS 10/10
```

Decision detail:

```text
expected=Pivot
actual=Pivot
```

The produced `launch-state.json` records:

```text
stage=pre_launch_test
decision=Pivot
promotion_adjustment=abandon the "smart coffee table" query and retarget slow-cooker queries if the SKU remains viable
next_loop_test=diagnose review/root-cause; Kill only if defects are inherent or non-salvageable
```

## Validation

```text
focused_contract_and_prompt_tests=13 passed, 1 warning
decision_gate=PASS 70/70
knowledge_quality=PASS 60/60
broader_opensku_regression=81 passed, 1 warning
py_compile=PASS
git diff --check=PASS
```

## Decision

Accepted.

The prior expected-decision failure was a useful semantic regression signal, not a runtime failure. The taxonomy fix now passes a real live agent rerun and the optional release-candidate decision gate. The boundary is:

```text
pre_launch_test search-fit mismatch defaults to Pivot
Kill only when the SKU or offer itself is not worth continuing
```

## Next

1. Add release-candidate scoring commands that can run `--decision-gate` across a selected multi-run acceptance set.
2. Continue Phase 10 documentation/demo packaging so reviewers can reproduce one full real run.
3. Continue toward Phase 11 full verification, especially frontend/UI evidence that has not been covered by this backend/eval node.
