# 2026-06-27 - OpenSKU Live Batch Orchestration

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: execute Phase 6 after deterministic scoring, by adding batch orchestration over OpenSKU benchmark cases.
- Scope: case-aware live runner input, batch CLI, batch reports, tests, docs, and one real live batch smoke.

## Thinking

The project needed more than a single "seven day package" demo. Phase 4 proved one live agent run could produce a valid artifact bundle, and Phase 5 proved deterministic scoring could judge cases, artifact bundles, and live-run evidence. The next gap was orchestration: the system needed a repeatable way to select benchmark cases, run them through the real agent path, and score the resulting evidence.

The key design constraint was authenticity. A batch runner that only changes `case_id` while still prompting the same coffee tumbler demo would be fake. Therefore the single live runner was made case-aware:

- it accepts `--case-file`
- it stages `opensku-case.json` without hidden expected-answer fields
- it stages `opensku-case-brief.json`
- it copies fixture files referenced by the case
- it builds a prompt from the case stage, category, brief, required claims, forbidden claims, and staged files

The prompt intentionally does not reveal:

- `expected_decision`
- `expected_decision_rationale`
- `scoring_notes`

The runner also preserves the data boundary: public benchmark fixtures are not private merchant telemetry. The agent must not invent GMV, CTR, CVR, ROI, ad spend, sales volume, refund rate, repeat purchase, margin, live inventory, live ranking, or verified uplift.

## Actions Executed

| Action | File or Command | Result |
|---|---|---|
| Added Phase 6 tests | `backend/tests/test_opensku_live_batch.py` | Covered case-aware prompt hiding, fixture staging, case planning, command construction, fake executor batch report, and plan-only semantics |
| Made single live runner case-aware | `evals/opensku/run_live_agent_validation.py` | Added `--case-file`, public case upload, fixture copy, and case-specific prompt |
| Added batch runner | `evals/opensku/run_live_batch.py` | Selects explicit cases, one case per stage, or sorted full suite; runs live child commands; scores run dirs; writes batch reports |
| Fixed plan-only semantics | `evals/opensku/run_live_batch.py` | Plan-only no longer scores missing live-run dirs as failures |
| Fixed child runtime environment | `evals/opensku/run_live_batch.py` | Child commands now use `uv run --project backend` so gateway dependencies load correctly |
| Hardened final response checker | `evals/opensku/run_live_agent_validation.py` | Accepted Chinese data-boundary wording such as `数据局限` and `数据边界` |
| Updated docs | `evals/opensku/README.md` | Added live batch usage, report paths, and backend uv project note |

## Important Failure and Fixes

### Failure 1: prompt test overmatched `Hold`

The first red test asserted the expected decision string should not appear anywhere in the prompt. That failed because the prompt legitimately lists the decision enum `Go/Pivot/Hold/Kill/Scale`. The test was corrected to check hidden fields and answer-revealing phrasing instead of banning legal enum words.

### Failure 2: test helper directory collision

The fake batch run helper wrote artifacts under the run directory before `_write_run_evidence()` created the same directory. The shared test helper now uses `mkdir(..., exist_ok=True)`.

### Failure 3: plan-only report showed fake failures

The first plan-only report had `batch-summary.md` status `PLAN`, but `summary.md` showed live-run failures because the runner scored missing run dirs. This was misleading. The runner now leaves planned records as `score_status=PLAN`, `score=0`, `max_score=0`, and only scores the case suite in plan-only mode.

### Failure 4: child live command used the wrong uv project

The first real batch smoke failed before the agent started:

```text
ModuleNotFoundError: No module named 'fastapi'
```

Root cause: `run_live_batch.py` launched `uv run python ...` from repo root, but gateway dependencies live in the backend uv project. The child command now uses:

```text
uv run --project backend python evals/opensku/run_live_agent_validation.py ...
```

### Failure 5: final response checker missed valid Chinese wording

The first completed live run produced all artifacts, used all five subagents, called the artifact writer, called `present_files`, avoided external search, and passed artifact validation. It still failed because the final response checker looked for `数据限制` but the agent wrote `数据局限`. This was a harness vocabulary issue, not a product boundary miss. A regression test now accepts `数据局限`, `数据边界`, and `私域指标`.

## Evidence

### Plan-only batch

Command:

```bash
uv run --project backend python evals/opensku/run_live_batch.py \
  --stage idea_only \
  --stage supplier_sample \
  --stage pre_launch_test \
  --stage soft_launch \
  --stage scale_iterate \
  --max-cases 5 \
  --case-id-prefix batch-plan \
  --report-name 2026-06-27-phase-6-live-batch-plan \
  --plan-only
```

Final report:

```text
evals/opensku/reports/2026-06-27-phase-6-live-batch-plan/
```

Key result:

```text
batch-summary.md: Status: PLAN
batch-summary.md: LIVE_BATCH_PLAN_READY
summary.md: Status: PASS
summary.md: Score: 20/20
planned_case_ids=['opensku-idea-001', 'opensku-supplier-001', 'opensku-prelaunch-001', 'opensku-softlaunch-001', 'opensku-scale-001']
```

### Real live batch smoke

Command:

```bash
uv run --project backend python evals/opensku/run_live_batch.py \
  --case-id opensku-idea-001 \
  --case-id-prefix batch-live-smoke \
  --report-name 2026-06-27-phase-6-live-batch-smoke \
  --timeout-seconds 600 \
  --reasoning-effort medium
```

Final output:

```text
LIVE_VALIDATION_PASSED
report_dir=evals/opensku/reports/2026-06-27-phase-6-live-batch-smoke
status=PASS
planned_case_ids=['opensku-idea-001']
```

Run evidence:

```text
docs/progress/runs/2026-06-27/batch-live-smoke-opensku-idea-001/
```

Report evidence:

```text
evals/opensku/reports/2026-06-27-phase-6-live-batch-smoke/
```

Score:

```text
Status: PASS
Score: 60/60
case-suite: 20/20
live-run: 40/40
```

Live run evidence highlights:

```text
run_status=success
model=deepseek/deepseek-v4-flash
present_files_called=True
artifact_writer_called=True
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
external_search_tool_calls=[]
artifact_count=10
validator status=PASS
missing_final_response_requirements=[]
final_response_consistency_errors=[]
```

The final response decision was `Hold` for the idea-only case. It did not claim private performance metrics. It explicitly stated that public benchmark data was used and private merchant metrics were unavailable.

## Validation

Focused Phase 6 tests:

```bash
cd backend
uv run pytest tests/test_opensku_live_batch.py -q
```

Result:

```text
6 passed, 1 warning
```

Live runner tests after data-boundary wording fix:

```bash
cd backend
uv run pytest tests/test_opensku_live_runner.py -q
```

Result:

```text
5 passed, 1 warning
```

Related regression:

```bash
cd backend
uv run pytest tests/test_opensku_live_batch.py tests/test_opensku_scoring.py tests/test_opensku_live_runner.py tests/test_opensku_cases.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_artifact_validators.py tests/test_opensku_benchmark_tool_policy.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q
uv run python -m py_compile ../evals/opensku/run_live_batch.py ../evals/opensku/run_live_agent_validation.py ../evals/opensku/scoring.py
```

Result before the final live rerun:

```text
60 passed, 1 warning
```

## Current Limitations

- Only one real live batch smoke was executed in this phase. It proves the orchestration path, not all 30 benchmark cases.
- The live smoke relies on the currently configured DeepSeek model and network access.
- Public fixtures remain benchmark inputs. They are not private merchant telemetry.
- The final PASS run used the artifact writer's built-in validation plus the live runner's external validator. It did not require fake row counts, fake revenue, or fake uplift.

## Decision

Phase 6 live batch orchestration is accepted for a one-case real smoke and five-stage plan report. The system now has a credible path from benchmark cases to live agent execution to deterministic evidence scoring.

## Next

1. Run a staged batch of 5 real cases, one per launch stage, when token/cost budget is acceptable.
2. Add optional retry policy for transient live model or network failures.
3. Add a UI/report surface for `batch-summary.md` and `scores.json`.
4. Consider a later LLM-judge layer only after deterministic checks remain stable across more live runs.
