# 2026-06-27 - OpenSKU 10-Run Live Acceptance

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: complete the execution-plan requirement of at least 10 real live OpenSKU agent runs, with 2 runs per launch stage.
- Scope: second five-stage batch, failure triage, prompt/contract hardening, one targeted rerun, 10-run aggregate scoring, and focused regression.

## Thinking

The first five-stage batch proved breadth across `idea_only`, `supplier_sample`, `pre_launch_test`, `soft_launch`, and `scale_iterate`. The next recruiting-grade proof is repeatability: each stage should have a second non-duplicate live case that exercises the same real runtime path.

This phase deliberately keeps the bar high:

- live gateway/runtime/model/subagent/tool path only, no mocked replay
- all five ecommerce specialist subagents observed per accepted run
- `write_opensku_artifact_bundle` and `present_files` required
- runtime external-search gate must remove broad search tools in benchmark-fixture mode
- artifact validator must pass on the generated bundle
- final response must state stage, decision, next-loop test, promotion adjustment, data limitations, and artifact list
- public fixtures are treated as benchmark evidence, not private merchant telemetry

## Cases

Second-stage cases selected:

```text
opensku-idea-002
opensku-supplier-002
opensku-prelaunch-002
opensku-softlaunch-002
opensku-scale-002
```

These add one additional case per stage and cover traps including forbidden private metrics, uploaded-data simulation, unsupported claims, promotion replanning, and knowledge deltas.

## Actions Executed

| Action | Command or File | Result |
|---|---|---|
| Ran second five-stage live batch | `uv run --project backend python evals/opensku/run_live_batch.py --case-id opensku-idea-002 --case-id opensku-supplier-002 --case-id opensku-prelaunch-002 --case-id opensku-softlaunch-002 --case-id opensku-scale-002 --case-id-prefix batch-live-stage2 --report-name 2026-06-27-phase-8-live-stage2-batch --timeout-seconds 900 --reasoning-effort medium` | Initial batch scored `210/220`; first four cases passed, `opensku-scale-002` failed final-response consistency |
| Inspected failing run | `docs/progress/runs/2026-06-27/batch-live-stage2-opensku-scale-002/` | Runtime, subagents, writer, presenter, and artifact validator all passed; final response claimed `evidence-ledger.json` had 8 entries while the actual artifact had 5 |
| Added red test | `backend/tests/test_opensku_live_runner.py::test_live_prompt_requires_plain_filename_artifact_list_without_counts` | Failed before prompt hardening |
| Hardened final-response contract | `evals/opensku/run_live_agent_validation.py`, `skills/custom/ecom-launch/SKILL.md`, `agents/ecom-launch/SOUL.md`, `docs/ecom-launch/manual-run-prompt.md`, `backend/tests/test_ecom_launch_contract.py` | Final artifact list must be filenames only; no per-file descriptions, evidence counts, row counts, or entry counts |
| Verified focused tests | `uv run --project backend pytest backend/tests/test_opensku_live_runner.py::test_live_prompt_requires_plain_filename_artifact_list_without_counts backend/tests/test_ecom_launch_contract.py -q` | `4 passed, 1 warning` |
| Reran failed scale case only | `uv run --project backend python evals/opensku/run_live_batch.py --case-id opensku-scale-002 --case-id-prefix batch-live-stage2-rerun --report-name 2026-06-27-phase-8-live-stage2-scale-rerun --timeout-seconds 900 --reasoning-effort medium` | `LIVE_VALIDATION_PASSED`; final-response consistency errors cleared |
| Scored 10 accepted live runs | `uv run --project backend python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases ... --report-name 2026-06-27-phase-8-live-10run-score` | `Status: PASS`, `Score: 420/420` |

## Failure Triage

The initial `batch-live-stage2-opensku-scale-002` failure was not an artifact failure:

```text
run_status=success
present_files_called=True
artifact_writer_called=True
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
external_search_tool_calls=[]
artifact_count=10
validator status=PASS
missing_final_response_requirements=[]
final_response_consistency_errors=['final response claims evidence-ledger.json has 8 entries, expected 5']
```

The real `evidence-ledger.json` contained 5 entries:

```text
EVID-001 product_context
EVID-002 review_language_sample
EVID-003 public_catalog_context
EVID-004 GMV unavailable
EVID-005 launch_decision
```

Decision: keep the checker strict. The model was wrong to annotate the artifact list with a guessed evidence count. The fix was to harden the final-response contract and rerun the failed case through the real agent path.

## Accepted Evidence

Second-stage accepted run directories:

```text
docs/progress/runs/2026-06-27/batch-live-stage2-opensku-idea-002/
docs/progress/runs/2026-06-27/batch-live-stage2-opensku-supplier-002/
docs/progress/runs/2026-06-27/batch-live-stage2-opensku-prelaunch-002/
docs/progress/runs/2026-06-27/batch-live-stage2-opensku-softlaunch-002/
docs/progress/runs/2026-06-27/batch-live-stage2-rerun-opensku-scale-002/
```

Scale rerun evidence:

```text
case_id=batch-live-stage2-rerun-opensku-scale-002
run_status=success
present_files_called=True
artifact_writer_called=True
missing_final_response_requirements=[]
final_response_consistency_errors=[]
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
artifact_count=10
validator status=PASS
LIVE_VALIDATION_PASSED
```

10-run aggregate report:

```text
evals/opensku/reports/2026-06-27-phase-8-live-10run-score/
```

Result:

```text
Status: PASS
Score: 420/420
case-suite: 20/20
10 live runs: 10 * 40/40
```

## Data Boundary

These runs use public benchmark fixtures and public-fixture-as-uploaded simulation. They are not private merchant telemetry.

Do not claim this proves real GMV, CTR, CVR, ROI, CAC, ad spend, sales volume, refund rate, repeat purchase rate, margin, live ranking, or verified uplift. The accepted proof is narrower and stronger: OpenSKU can run a long, staged, evidence-governed launch loop through the real agent stack and reject unsupported commercial claims.

## Decision

The 10-run live acceptance requirement is complete.

The backend/eval hardening track is now substantially complete for the current execution plan. Remaining work should shift toward UI/demo evidence, retry/resume policy for long batches, and final portfolio packaging.
