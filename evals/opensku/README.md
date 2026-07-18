# OpenSKU-Bench

> **LEGACY — READ ONLY.** This benchmark belongs to the archived OpenSKU/EcomLaunch product. Its cases, reports, replayable evidence and historical PASS scores are not Commerce Case Agent tests or release gates. Preserve them for provenance; do not use them to claim the new Agent works.

OpenSKU-Bench is the benchmark-case layer for OpenSKU's evidence-governed adaptive SKU launch loop.

The benchmark uses public ecommerce fixtures as reproducible inputs. It does not treat those fixtures as live merchant telemetry, and it does not allow private metrics such as GMV, CTR, CVR, ROI, ad spend, margin, or verified uplift unless those fields are explicitly present in the case input.

## Files

```text
evals/opensku/case_schema.json
evals/opensku/cases/
evals/opensku/fixtures/
evals/opensku/build_cases_from_samples.py
evals/opensku/validate_cases.py
evals/opensku/print_case_matrix.py
evals/opensku/score_benchmark.py
evals/opensku/scoring.py
evals/opensku/run_live_agent_validation.py
evals/opensku/run_live_batch.py
evals/opensku/release_candidate_gate.py
evals/opensku/run_release_candidate_gate.py
evals/opensku/reports/
```

## Validation

Run:

```bash
uv run python evals/opensku/validate_cases.py
uv run python evals/opensku/print_case_matrix.py
```

The suite is valid only when:

- exactly 30 cases exist.
- stage counts are 6 idea-only, 6 supplier-sample, 6 pre-launch-test, 8 soft-launch, and 4 scale-iterate.
- every case has a source dataset and a stage.
- every case has an expected decision and rationale.
- at least 10 cases include uploaded-data simulation.
- at least 10 cases include public-signal context.
- at least 5 cases catch forbidden private metric hallucination.
- at least 5 cases catch unsupported product/spec/policy claims.

## Scoring

OpenSKU-Bench scoring is evidence-based. It does not infer real commercial uplift. It scores three inspectable layers:

| Layer | Max | What It Checks |
|---|---:|---|
| Case suite | 20 | 30-case count, stage coverage, tag/trap coverage, source references |
| Artifact bundle | 40 | artifact validator pass/fail, required artifact coverage, evidence boundary, loop artifacts |
| Live run evidence | 40 | real run success, `present_files`, all five ecommerce roles, writer tool, external-search gate, artifact manifest, validator output, final-response coverage/consistency |

Generate a PASS report from the current benchmark suite, one golden artifact bundle, and the latest passing live run:

```bash
uv run python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --artifact-bundle evals/opensku/fixtures/golden/golden-001 \
  --live-run docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001-bundle-writer-final-check \
  --report-name 2026-06-27-phase-5-scoring-smoke
```

Expected output:

```text
status=PASS
score=100/100
```

The report is written to:

```text
evals/opensku/reports/2026-06-27-phase-5-scoring-smoke/
├── summary.md
├── scores.json
└── failures.md
```

Generate a negative-control report that must fail on a forbidden private metric boundary:

```bash
uv run python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --artifact-bundle evals/opensku/fixtures/broken/broken-003 \
  --report-name 2026-06-27-phase-5-scoring-broken-check
```

Expected output:

```text
status=FAIL
score=30/60
```

## Live Batch Runner

`run_live_batch.py` orchestrates real live validations across selected OpenSKU benchmark cases. It is intentionally a runner, not a fake evaluator: when `--plan-only` is not set, each selected case invokes `run_live_agent_validation.py`, which uses the real gateway app, auth/CSRF flow, run manager, lead-agent runtime, live model, ecommerce subagents, artifact writer, and artifact validation path.

Plan a batch without spending model calls:

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

Expected output:

```text
status=PLAN
planned_case_ids=['opensku-idea-001', 'opensku-supplier-001', 'opensku-prelaunch-001', 'opensku-softlaunch-001', 'opensku-scale-001']
```

The plan report is written to:

```text
evals/opensku/reports/2026-06-27-phase-6-live-batch-plan/
├── summary.md
├── scores.json
├── failures.md
├── batch-records.json
└── batch-summary.md
```

Run one real smoke case:

```bash
uv run --project backend python evals/opensku/run_live_batch.py \
  --case-id opensku-idea-001 \
  --case-id-prefix batch-live-smoke \
  --report-name 2026-06-27-phase-6-live-batch-smoke \
  --timeout-seconds 600 \
  --reasoning-effort medium
```

Expected output:

```text
status=PASS
planned_case_ids=['opensku-idea-001']
```

The live run evidence is written to:

```text
docs/progress/runs/2026-06-27/batch-live-smoke-opensku-idea-001/
├── artifacts-manifest.json
├── final-response.md
├── notes.md
├── raw-run-events.json
├── run-log.md
└── validator-output.txt
```

The batch score report is written to:

```text
evals/opensku/reports/2026-06-27-phase-6-live-batch-smoke/
├── summary.md
├── scores.json
├── failures.md
├── batch-records.json
└── batch-summary.md
```

`run_live_batch.py` uses `uv run --project backend` for child live runs because the gateway/runtime dependencies live in the backend project environment.

Score already-written live run evidence without spending model calls:

```bash
uv run --project backend python evals/opensku/run_live_batch.py \
  --stage idea_only \
  --stage supplier_sample \
  --stage pre_launch_test \
  --stage soft_launch \
  --stage scale_iterate \
  --max-cases 5 \
  --case-id-prefix batch-live-5stage \
  --report-name 2026-06-27-phase-7-live-5stage-batch-final \
  --score-existing
```

This mode is useful after a long batch run when only one failed case had to be rerun. It does not invoke the live agent; it reads existing run directories under `docs/progress/runs/<date>/<prefix>-<case-id>/` and writes a fresh batch report.

The Phase 7 five-stage report is:

```text
evals/opensku/reports/2026-06-27-phase-7-live-5stage-batch-final/
├── summary.md
├── scores.json
├── failures.md
├── batch-records.json
└── batch-summary.md
```

Score the 10-run acceptance set without spending model calls by passing the
existing run evidence directories directly to `score_benchmark.py`:

```bash
uv run --project backend python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --live-run docs/progress/runs/2026-06-27/batch-live-5stage-opensku-idea-001 \
  --live-run docs/progress/runs/2026-06-27/batch-live-5stage-opensku-supplier-001 \
  --live-run docs/progress/runs/2026-06-27/batch-live-5stage-opensku-prelaunch-001 \
  --live-run docs/progress/runs/2026-06-27/batch-live-5stage-opensku-softlaunch-001 \
  --live-run docs/progress/runs/2026-06-27/batch-live-5stage-opensku-scale-001 \
  --live-run docs/progress/runs/2026-06-27/batch-live-stage2-opensku-idea-002 \
  --live-run docs/progress/runs/2026-06-27/batch-live-stage2-opensku-supplier-002 \
  --live-run docs/progress/runs/2026-06-27/batch-live-stage2-opensku-prelaunch-002 \
  --live-run docs/progress/runs/2026-06-27/batch-live-stage2-opensku-softlaunch-002 \
  --live-run docs/progress/runs/2026-06-27/batch-live-stage2-rerun-opensku-scale-002 \
  --report-name 2026-06-27-phase-8-live-10run-score
```

Expected output:

```text
status=PASS
score=420/420
```

The 10-run acceptance report is:

```text
evals/opensku/reports/2026-06-27-phase-8-live-10run-score/
├── summary.md
├── scores.json
└── failures.md
```

## Expected Decision Gate

The default live-run score validates execution integrity: real runtime path,
subagents, artifact writer, validator output, external-search gate, manifest, and
final-response contract. It does not, by itself, prove that the final
Go/Pivot/Hold/Kill/Scale decision matches the benchmark's hidden expected
decision.

Enable the expected-decision gate when a report should fail on semantic decision
mismatch:

```bash
uv run --project backend python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --live-run docs/progress/runs/2026-06-27/live-knowledge-injection-prelaunch-002 \
  --decision-gate \
  --report-name 2026-06-27-phase-11-expected-decision-gate-prelaunch-002
```

Expected output for the current prelaunch injected run:

```text
status=FAIL
score=65/70
```

This is an intentional failure: the live run passed execution scoring, but its
final `launch-state.json` decision was `Kill` while
`evals/opensku/cases/opensku-prelaunch-002.json` expects `Pivot`.

The report is written to:

```text
evals/opensku/reports/2026-06-27-phase-11-expected-decision-gate-prelaunch-002/
├── summary.md
├── scores.json
└── failures.md
```

Failure detail:

```text
expected=Pivot
actual=Kill
```

After tightening the `pre_launch_test` Pivot/Kill taxonomy, rerun the same case
through the real live agent path:

```bash
uv run --project backend python evals/opensku/run_live_agent_validation.py \
  --case-id live-decision-taxonomy-prelaunch-002 \
  --case-file evals/opensku/cases/opensku-prelaunch-002.json \
  --date 2026-06-27 \
  --timeout-seconds 900 \
  --reasoning-effort medium \
  --knowledge-dir docs/knowledge/opensku
```

Expected output:

```text
status=PASS
LIVE_VALIDATION_PASSED
```

Score the rerun with the decision gate:

```bash
uv run --project backend python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --live-run docs/progress/runs/2026-06-27/live-decision-taxonomy-prelaunch-002 \
  --decision-gate \
  --report-name 2026-06-27-phase-12-prelaunch-taxonomy-decision-gate
```

Expected output:

```text
status=PASS
score=70/70
expected=Pivot
actual=Pivot
```

The report is written to:

```text
evals/opensku/reports/2026-06-27-phase-12-prelaunch-taxonomy-decision-gate/
├── summary.md
├── scores.json
└── failures.md
```

Use this gate for release-candidate validation. Use the default score when the
question is only whether the live agent runtime and artifact contract executed
correctly.

## Release-Candidate Gate

Use `run_release_candidate_gate.py` when a release-candidate check should score
a named set of real live-run evidence with expected-decision validation enabled
by default.

The first passing multi-stage RC gate is:

```bash
uv run --project backend python evals/opensku/run_release_candidate_gate.py \
  --candidate-file evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json \
  --report-name 2026-06-27-rc1-five-stage-decision-gate
```

Expected output:

```text
candidate=2026-06-27-rc1-five-stage
live_run_count=5
decision_gate=True
status=PASS
score=280/280
```

The report is written to:

```text
evals/opensku/reports/2026-06-27-rc1-five-stage-decision-gate/
├── summary.md
├── scores.json
└── failures.md
```

The candidate file is intentionally explicit:

```text
evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json
```

It covers one accepted real live run per launch stage. It is useful as the first
semantic release gate, but it is not the final 10-run release gate.

The first 10-run probe with `--decision-gate` intentionally failed:

```text
evals/opensku/reports/2026-06-27-rc-gate-probe/
status=FAIL
score=500/520
opensku-prelaunch-001: expected=Go, actual=Pivot
opensku-idea-002: expected=Pivot, actual=Hold
opensku-supplier-002: expected=Pivot, actual=Hold
opensku-softlaunch-002: expected=Pivot, actual=Hold
```

Those failures were resolved by Go/Pivot/Hold taxonomy hardening, three real
reruns, and one benchmark-case correction for a contradictory WANDS
query/product/category mismatch.

The current reviewer-facing 10-run release candidate is:

```bash
uv run --project backend python evals/opensku/run_release_candidate_gate.py \
  --candidate-file evals/opensku/release_candidates/2026-06-28-rc2-10run.json \
  --report-name 2026-06-28-rc2-10run-decision-gate
```

Expected output:

```text
candidate=2026-06-28-rc2-10run
live_run_count=10
decision_gate=True
status=PASS
score=530/530
```

The report is written to:

```text
evals/opensku/reports/2026-06-28-rc2-10run-decision-gate/
├── summary.md
├── scores.json
└── failures.md
```

The RC2 candidate has two accepted real live runs per launch stage:

| Stage | Case IDs |
|---|---|
| `idea_only` | `opensku-idea-001`, `opensku-idea-002` |
| `supplier_sample` | `opensku-supplier-001`, `opensku-supplier-002` |
| `pre_launch_test` | `opensku-prelaunch-001`, `opensku-prelaunch-002` |
| `soft_launch` | `opensku-softlaunch-001`, `opensku-softlaunch-002` |
| `scale_iterate` | `opensku-scale-001`, `opensku-scale-002` |

## Knowledge Sedimentation

Accepted live runs produce `knowledge-deltas.json`. Ingest those deltas into a
durable local knowledge base:

```bash
uv run --project backend python scripts/opensku/ingest_knowledge_deltas.py \
  --runs docs/progress/runs \
  --output docs/knowledge/opensku \
  --min-records 20
```

Expected output for the current RC2 snapshot:

```text
status=PASS
accepted_run_count=21
record_count=63
pattern_count=13
```

Run a real cross-stage live validation with the current tightened knowledge reuse selector:

```bash
uv run --project backend python evals/opensku/run_live_agent_validation.py \
  --case-id live-knowledge-injection-prelaunch-002 \
  --case-file evals/opensku/cases/opensku-prelaunch-002.json \
  --date 2026-06-27 \
  --timeout-seconds 900 \
  --reasoning-effort medium \
  --knowledge-dir docs/knowledge/opensku
```

Expected output:

```text
LIVE_VALIDATION_PASSED
```

The accepted run writes `injected_knowledge_patterns` into:

```text
docs/progress/runs/2026-06-27/live-knowledge-injection-prelaunch-002/artifacts-manifest.json
```

The current cross-stage accepted run injected these snapshot-local pattern IDs:

```text
kp_0008 pitfall  -> private metric boundary
kp_0009 process  -> runtime artifact writer plus validator
kp_0006 decision -> pre_launch_test Pivot pattern
kp_0002 decision -> pre_launch_test Hold pattern
```

`kp_XXXX` IDs are generated from the current aggregate pattern order and can drift after
new knowledge is ingested. Promotion therefore matches injected knowledge by stable
`reuse_key` (`type|scope|statement`) before falling back to ID. Decision-pattern
promotion also requires the final `launch-state.json` decision to match the pattern
statement; a successful run does not verify a decision pattern that the final evidence
does not support.

Score the current cross-stage run:

```bash
uv run --project backend python evals/opensku/score_benchmark.py \
  --cases-dir evals/opensku/cases \
  --live-run docs/progress/runs/2026-06-27/live-knowledge-injection-prelaunch-002 \
  --report-name 2026-06-27-phase-10-cross-stage-knowledge-injection-score
```

Expected output:

```text
status=PASS
score=60/60
```

Promote reused patterns only after a later successful run:

```bash
uv run --project backend python scripts/opensku/promote_knowledge_maturity.py \
  --knowledge docs/knowledge/opensku \
  --runs docs/progress/runs \
  --min-promotions 1
```

Expected output for the current RC2 snapshot after a fresh ingest:

```text
status=PASS
reuse_evidence_count=31
promoted_count=4
verified_reuse_pattern_count=4
```

Score the generated knowledge base:

```bash
uv run --project backend python evals/opensku/scorers/knowledge_delta_quality.py \
  --knowledge docs/knowledge/opensku \
  --min-records 20 \
  --min-reused-patterns 5
```

Expected output:

```text
status=PASS
score=60/60
```

The generated knowledge base is written to:

```text
docs/knowledge/opensku/
├── README.md
├── ingest-report.json
├── knowledge-deltas.jsonl
├── promotion-report.json
└── patterns.json
```

## Fixture Boundary

The current generated cases cite small samples under:

```text
data/opensku/samples/
data/opensku/schemas/
```

These samples were loaded from real public URLs in Phase 1. They are not synthetic rows and they are not private merchant data.
