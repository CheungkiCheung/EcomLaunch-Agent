# OpenSKU Reviewer Guide

This guide is for a reviewer who wants to validate OpenSKU without guessing
which files are authoritative.

## One-Line Positioning

OpenSKU is an evidence-governed adaptive SKU launch loop:

```text
real ecommerce fixtures + real agent execution + artifact contracts + eval gates + knowledge sedimentation + inspectable UI
```

It is not a fixed seven-day plan generator. The next launch loop can be 3, 7,
14, or 30 days depending on launch stage, available evidence, operational risk,
and feedback quality.

## What To Inspect First

| Question | Start Here |
|---|---|
| What is the final release-candidate result? | `evals/opensku/reports/2026-06-28-rc2-10run-decision-gate/summary.md` |
| Which live runs are included? | `evals/opensku/release_candidates/2026-06-28-rc2-10run.json` |
| Were the four semantic mismatches fixed honestly? | `docs/progress/2026-06-28-final-completion.md` |
| Is knowledge sedimentation real or just a wiki? | `docs/knowledge/opensku/README.md`, `docs/knowledge/opensku/promotion-report.json` |
| What does the UI look like? | `docs/progress/screenshots/2026-06-28-opensku-war-room.png` |
| What remains non-production? | The limitations section in this file and the evidence matrix |

## Current Release Candidate

The current reviewer-facing gate is RC2:

```bash
uv run --project backend python evals/opensku/run_release_candidate_gate.py \
  --candidate-file evals/opensku/release_candidates/2026-06-28-rc2-10run.json \
  --report-name 2026-06-28-rc2-10run-decision-gate
```

Expected result:

```text
candidate=2026-06-28-rc2-10run
live_run_count=10
decision_gate=True
status=PASS
score=530/530
```

The gate scores two accepted real live runs per launch stage:

| Stage | Case IDs |
|---|---|
| `idea_only` | `opensku-idea-001`, `opensku-idea-002` |
| `supplier_sample` | `opensku-supplier-001`, `opensku-supplier-002` |
| `pre_launch_test` | `opensku-prelaunch-001`, `opensku-prelaunch-002` |
| `soft_launch` | `opensku-softlaunch-001`, `opensku-softlaunch-002` |
| `scale_iterate` | `opensku-scale-001`, `opensku-scale-002` |

## Real Agent Evidence Boundary

The RC2 live-run directories under `docs/progress/runs/` are real agent
execution evidence. They are not mock-only fixtures. Each accepted live run
contains runtime output such as:

```text
run-log.md
raw-run-events.json
final-response.md
artifacts-manifest.json
validator-output.txt
```

The frontend real-backend Playwright test is a replay-backed UI regression. It
is useful for UI/protocol stability, but it is not counted as fresh live model
evidence. The release-candidate gate is the acceptance source for agent
behavior.

## Knowledge Sedimentation

The knowledge base is generated from accepted run artifacts:

```text
docs/knowledge/opensku/knowledge-deltas.jsonl
docs/knowledge/opensku/patterns.json
docs/knowledge/opensku/ingest-report.json
docs/knowledge/opensku/promotion-report.json
```

Current snapshot:

```text
accepted_run_count=21
record_count=63
pattern_count=13
reuse_evidence_count=31
promoted_count=4
verified_reuse_pattern_count=4
quality_score=60/60
```

This is intentionally not an LLM wiki. Patterns are extracted from accepted
runs, selected into later runs, and promoted only after successful reuse.

## UI Evidence

The War Room screenshot is:

```text
docs/progress/screenshots/2026-06-28-opensku-war-room.png
```

The page shows:

- stage diagnosis
- decision status
- artifact readiness
- explicit private-metric boundary
- selected launch crew agent
- live motion rules
- motion queue
- visual war room with background, workstations, props, and six agents

The canvas implementation includes a static visual fallback under the Pixi layer
so browser screenshots remain inspectable even when WebGL or canvas painting is
unreliable in automation.

## Reproduction Commands

Backend and eval regression:

```bash
cd backend
uv run pytest \
  tests/test_opensku_live_batch.py \
  tests/test_opensku_scoring.py \
  tests/test_opensku_release_candidate_gate.py \
  tests/test_opensku_live_runner.py \
  tests/test_opensku_cases.py \
  tests/test_opensku_artifact_writer_tool.py \
  tests/test_opensku_artifact_validator_tool.py \
  tests/test_opensku_artifact_validators.py \
  tests/test_opensku_benchmark_tool_policy.py \
  tests/test_opensku_knowledge_ingest.py \
  tests/test_opensku_knowledge_quality.py \
  tests/test_opensku_knowledge_context.py \
  tests/test_opensku_knowledge_promotion.py \
  tests/test_ecom_launch_contract.py \
  tests/test_tool_args_schema_no_pydantic_warning.py -q
```

Frontend regression:

```bash
cd frontend
pnpm typecheck
pnpm test -- tests/unit/components/workspace/ecom-launch
pnpm test:e2e -- tests/e2e/artifact-preview.spec.ts tests/e2e/agent-chat.spec.ts
pnpm exec playwright test --config=playwright.real-backend.config.ts
```

Knowledge refresh:

```bash
uv run --project backend python scripts/opensku/ingest_knowledge_deltas.py \
  --runs docs/progress/runs \
  --output docs/knowledge/opensku \
  --min-records 20

uv run --project backend python scripts/opensku/promote_knowledge_maturity.py \
  --knowledge docs/knowledge/opensku \
  --runs docs/progress/runs \
  --min-promotions 1

uv run --project backend python evals/opensku/scorers/knowledge_delta_quality.py \
  --knowledge docs/knowledge/opensku \
  --min-records 20 \
  --min-reused-patterns 5
```

## Limitations

- Public ecommerce fixtures are real public benchmark/sample data, not private
  merchant telemetry.
- OpenSKU does not claim access to GMV, CTR, CVR, ROI, ad spend, margin,
  refunds, repeat purchases, sales volume, or verified uplift unless a user
  uploads those fields.
- The project does not include production ecommerce platform connectors.
- The UI replay test is replay-backed. It validates rendering and protocol
  stability, not fresh live-model behavior.
- The War Room is an inspectable product UI. The release-candidate gate remains
  the source of truth for agent decision quality.
