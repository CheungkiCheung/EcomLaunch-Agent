# 2026-06-27 - OpenSKU Five-Stage Live Batch

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: execute the next step after Phase 6 by running one real live OpenSKU case for each launch stage.
- Scope: five real live runs, failure triage, checker hardening, one targeted rerun, score-existing aggregation, tests, and docs.

## Thinking

Phase 6 proved one case can move through the real gateway/model/subagent/artifact/scoring path. The next useful recruiting-grade proof is stage breadth: the same system should work across `idea_only`, `supplier_sample`, `pre_launch_test`, `soft_launch`, and `scale_iterate`.

This is intentionally not a "generate a seven-day package" demo. Each case goes through the real runtime path:

- FastAPI gateway and auth/CSRF path
- lead-agent construction with `agent_name=ecom-launch`
- live DeepSeek model calls
- five ecommerce specialist subagents
- runtime external-search gate
- artifact writer
- artifact presentation
- artifact validator
- deterministic live-run scoring

The batch still uses public benchmark fixtures. These are not private merchant telemetry. No report claims real GMV, CTR, CVR, ROI, ad spend, sales volume, refund rate, repeat purchase rate, margin, live ranking, or verified uplift.

## Actions Executed

| Action | Command or File | Result |
|---|---|---|
| Ran five-stage live batch | `uv run --project backend python evals/opensku/run_live_batch.py --stage idea_only --stage supplier_sample --stage pre_launch_test --stage soft_launch --stage scale_iterate --max-cases 5 --case-id-prefix batch-live-5stage --report-name 2026-06-27-phase-7-live-5stage-batch --timeout-seconds 900 --reasoning-effort medium` | Initial aggregate failed at 210/220 because `pre_launch_test` final-response wording was not recognized |
| Inspected failing run | `docs/progress/runs/2026-06-27/batch-live-5stage-opensku-prelaunch-001/final-response.md` | The response did include valid data-boundary language under `指标限制` |
| Hardened final response checker | `evals/opensku/run_live_agent_validation.py` and `backend/tests/test_opensku_live_runner.py` | Added support for `指标限制`, `私有商户指标`, `无价格数据`, and related wording |
| Added score-existing mode | `evals/opensku/run_live_batch.py` and `backend/tests/test_opensku_live_batch.py` | Allows final aggregation from existing run directories without rerunning already passing cases |
| Reran failed case only | `uv run --project backend python evals/opensku/run_live_batch.py --case-id opensku-prelaunch-001 --case-id-prefix batch-live-5stage --report-name 2026-06-27-phase-7-prelaunch-rerun --timeout-seconds 900 --reasoning-effort medium` | `LIVE_VALIDATION_PASSED`, `40/40` |
| Generated final five-stage aggregate | `uv run --project backend python evals/opensku/run_live_batch.py --stage idea_only --stage supplier_sample --stage pre_launch_test --stage soft_launch --stage scale_iterate --max-cases 5 --case-id-prefix batch-live-5stage --report-name 2026-06-27-phase-7-live-5stage-batch-final --score-existing` | `Status: PASS`, `Score: 220/220` |

## Initial Batch Evidence

Report:

```text
evals/opensku/reports/2026-06-27-phase-7-live-5stage-batch/
```

Initial result:

```text
Status: FAIL
Score: 210/220
idea_only: 40/40 PASS
supplier_sample: 40/40 PASS
pre_launch_test: 30/40 FAIL
soft_launch: 40/40 PASS
scale_iterate: 40/40 PASS
```

The prelaunch live run was not a tool or artifact failure:

```text
run_status=success
present_files_called=True
artifact_writer_called=True
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
external_search_tool_calls=[]
artifact_count=10
validator status=PASS
missing_final_response_requirements=['data_limitations']
```

The final response contained:

```text
指标限制: 本次验证仅基于 WANDS 公共基准测试数据，不包含任何私有商户指标。
无价格数据、销售额、CTR、CVR、ROI、退款率、广告支出或实时排名数据可供参考。
```

Therefore the failure was attributed to checker vocabulary, not to a data-boundary miss by the agent.

## Final Evidence

Final aggregate report:

```text
evals/opensku/reports/2026-06-27-phase-7-live-5stage-batch-final/
```

Final result:

```text
Status: PASS
Score: 220/220
case-suite: 20/20
idea_only live-run: 40/40
supplier_sample live-run: 40/40
pre_launch_test live-run: 40/40
soft_launch live-run: 40/40
scale_iterate live-run: 40/40
```

Batch summary:

```text
LIVE_VALIDATION_PASSED
```

Run evidence directories:

```text
docs/progress/runs/2026-06-27/batch-live-5stage-opensku-idea-001/
docs/progress/runs/2026-06-27/batch-live-5stage-opensku-supplier-001/
docs/progress/runs/2026-06-27/batch-live-5stage-opensku-prelaunch-001/
docs/progress/runs/2026-06-27/batch-live-5stage-opensku-softlaunch-001/
docs/progress/runs/2026-06-27/batch-live-5stage-opensku-scale-001/
```

All five final run logs show:

```text
Status: PASS
run_status: success
present_files_called: True
artifact_writer_called: True
external_search_tool_calls: []
missing_final_response_requirements: []
artifact_count: 10
```

## Validation

Focused tests after checker and score-existing changes:

```bash
cd backend
uv run pytest tests/test_opensku_live_runner.py -q
uv run pytest tests/test_opensku_live_batch.py -q
uv run python -m py_compile ../evals/opensku/run_live_batch.py ../evals/opensku/run_live_agent_validation.py
```

Observed results:

```text
tests/test_opensku_live_runner.py: 6 passed, 1 warning
tests/test_opensku_live_batch.py: 7 passed, 1 warning
```

## Decision

The five-stage live batch is accepted. OpenSKU now has live evidence that the same benchmark-driven agent loop works across all five launch stages, with deterministic scoring and stage-specific run logs.

## Current Limitations

- This is five representative cases, not all 30 benchmark cases.
- The final aggregate uses `--score-existing` after a targeted rerun, so it does not spend model calls on the four already-passing cases.
- Public benchmark fixtures remain public fixtures. They do not prove private merchant uplift.

## Next

1. Add a retry/resume policy for long live batches so transient final-response or network failures can be retried automatically.
2. Run larger batches by tag, especially `forbidden_metric_trap` and `uploaded_data_simulation`.
3. Surface `scores.json` and `batch-summary.md` in docs or UI for demo review.
