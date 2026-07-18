# 2026-06-27 - OpenSKU Knowledge Reuse Injection

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: close the loop from knowledge archive to execution memory.
- Scope: selector, prompt injection, live-run metadata, batch pass-through, real live validation, quality score, and maturity promotion.

## Thinking

The previous Phase 9 implementation generated `docs/knowledge/opensku/`, but future runs did not yet consume it. That made the knowledge base inspectable, not operational.

This milestone implements the next loop:

```text
patterns.json -> bounded pattern selection -> prompt injection -> live run evidence -> validator/scoring -> maturity promotion
```

Two guardrails were chosen:

- Pattern injection is bounded. The runner selects at most 5 patterns instead of pasting the whole knowledge base.
- Decision patterns must match the current stage before being injected or promoted. Cross-stage decision reuse is too easy to overfit.

## Actions Executed

| Action | Command / File | Result |
|---|---|---|
| Added red tests | `backend/tests/test_opensku_knowledge_context.py`, `backend/tests/test_opensku_live_runner.py` | Initially failed because `evals.opensku.knowledge_context` and runner arguments did not exist |
| Implemented selector | `evals/opensku/knowledge_context.py` | Loads `patterns.json`, infers stage matches, scores patterns, formats prompt context, serializes manifest metadata |
| Extended live runner | `evals/opensku/run_live_agent_validation.py` | Added `--knowledge-dir`, `--knowledge-limit`, prompt injection, and `injected_knowledge_patterns` manifest field |
| Extended batch runner | `evals/opensku/run_live_batch.py` | Added `--knowledge-dir` pass-through to child live validations |
| Added promotion tests | `backend/tests/test_opensku_knowledge_promotion.py` | Initially failed because promotion script did not exist |
| Implemented promotion | `scripts/opensku/promote_knowledge_maturity.py` | Promotes `draft -> verified` only after later successful injected live run |
| Ran focused tests | `uv run pytest tests/test_opensku_knowledge_context.py tests/test_opensku_live_runner.py tests/test_opensku_live_batch.py -q` | `19 passed, 1 warning` |
| Ran first real injected live validation | `uv run --project backend python evals/opensku/run_live_agent_validation.py --case-id live-knowledge-injection-opensku-idea-002 --case-file evals/opensku/cases/opensku-idea-002.json --date 2026-06-27 --timeout-seconds 900 --reasoning-effort medium --knowledge-dir docs/knowledge/opensku` | `LIVE_VALIDATION_PASSED` |
| Scored first injected live run | `uv run --project backend python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --live-run docs/progress/runs/2026-06-27/live-knowledge-injection-opensku-idea-002 --report-name 2026-06-27-phase-9-knowledge-injection-live-score` | `status=PASS`, `score=60/60` |
| Tightened selector | `evals/opensku/knowledge_context.py`, `scripts/opensku/promote_knowledge_maturity.py` | Decision patterns now require stage match before injection or promotion |
| Ran current tightened-selector live validation | `uv run --project backend python evals/opensku/run_live_agent_validation.py --case-id live-knowledge-injection-v2-opensku-idea-002 --case-file evals/opensku/cases/opensku-idea-002.json --date 2026-06-27 --timeout-seconds 900 --reasoning-effort medium --knowledge-dir docs/knowledge/opensku` | `LIVE_VALIDATION_PASSED` |
| Scored current injected live run | `uv run --project backend python evals/opensku/score_benchmark.py --cases-dir evals/opensku/cases --live-run docs/progress/runs/2026-06-27/live-knowledge-injection-v2-opensku-idea-002 --report-name 2026-06-27-phase-9-knowledge-injection-v2-live-score` | `status=PASS`, `score=60/60` |
| Rebuilt knowledge base | `uv run --project backend python scripts/opensku/ingest_knowledge_deltas.py --runs docs/progress/runs --output docs/knowledge/opensku --min-records 20` | `status=PASS`, `accepted_run_count=15`, `record_count=45`, `pattern_count=9` |
| Promoted reused patterns | `uv run --project backend python scripts/opensku/promote_knowledge_maturity.py --knowledge docs/knowledge/opensku --runs docs/progress/runs --min-promotions 1` | `status=PASS`, `reuse_evidence_count=8`, `verified_reuse_pattern_count=3`; reruns are idempotent, so `promoted_count=0` after the first promotion |
| Scored knowledge base | `uv run --project backend python evals/opensku/scorers/knowledge_delta_quality.py --knowledge docs/knowledge/opensku --min-records 20 --min-reused-patterns 5` | `status=PASS`, `score=60/60`, `record_count=45` |
| Ran final backend/eval regression | `uv run pytest tests/test_opensku_live_batch.py tests/test_opensku_scoring.py tests/test_opensku_live_runner.py tests/test_opensku_cases.py tests/test_opensku_artifact_writer_tool.py tests/test_opensku_artifact_validator_tool.py tests/test_opensku_artifact_validators.py tests/test_opensku_benchmark_tool_policy.py tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_ecom_launch_contract.py tests/test_tool_args_schema_no_pydantic_warning.py -q` | `74 passed, 1 warning` |
| Synced documentation | `evals/opensku/README.md`, `docs/knowledge/opensku/README.md`, this progress log | Updated current run path, score report, `accepted_run_count=15`, `record_count=45`, `reuse_evidence_count=8`, and `verified_reuse_pattern_count=3` |
| Re-ran focused reuse regression after doc sync | `cd backend && uv run pytest tests/test_opensku_knowledge_context.py tests/test_opensku_knowledge_promotion.py tests/test_opensku_live_runner.py tests/test_opensku_live_batch.py -q` | `21 passed, 1 warning` |
| Ran Python compile check | `uv run --project backend python -m py_compile evals/opensku/run_live_batch.py evals/opensku/run_live_agent_validation.py evals/opensku/knowledge_context.py scripts/opensku/promote_knowledge_maturity.py` | PASS |

## Evidence

Code:

```text
evals/opensku/knowledge_context.py
evals/opensku/run_live_agent_validation.py
evals/opensku/run_live_batch.py
scripts/opensku/promote_knowledge_maturity.py
backend/tests/test_opensku_knowledge_context.py
backend/tests/test_opensku_knowledge_promotion.py
backend/tests/test_opensku_live_runner.py
backend/tests/test_opensku_live_batch.py
```

Real live runs:

```text
docs/progress/runs/2026-06-27/live-knowledge-injection-opensku-idea-002/
├── artifacts-manifest.json
├── final-response.md
├── notes.md
├── raw-run-events.json
├── run-log.md
└── validator-output.txt

docs/progress/runs/2026-06-27/live-knowledge-injection-v2-opensku-idea-002/
├── artifacts-manifest.json
├── final-response.md
├── notes.md
├── raw-run-events.json
├── run-log.md
└── validator-output.txt
```

Score reports:

```text
evals/opensku/reports/2026-06-27-phase-9-knowledge-injection-live-score/
├── failures.md
├── scores.json
└── summary.md

evals/opensku/reports/2026-06-27-phase-9-knowledge-injection-v2-live-score/
├── failures.md
├── scores.json
└── summary.md
```

Knowledge base:

```text
docs/knowledge/opensku/
├── README.md
├── ingest-report.json
├── knowledge-deltas.jsonl
├── patterns.json
└── promotion-report.json
```

Injected patterns in the current tightened-selector accepted live run:

```text
kp_0008 pitfall verified -> private metric boundary
kp_0009 process verified -> runtime artifact writer plus validator
kp_0001 decision verified -> idea_only Hold pattern
```

The first run injected two cross-stage decision patterns before the selector was tightened. The current run is the acceptance run because it injected only stage-compatible decision knowledge. The promotion script now blocks cross-stage decision promotion, and the knowledge base was rebuilt before the final promotion pass.

Promoted patterns after tightened promotion:

```text
kp_0001 verified
kp_0008 verified
kp_0009 verified
```

## Validation

Current live run result:

```text
run_status=success
present_files_called=True
artifact_writer_called=True
subagent_types=['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
artifact_count=10
validator status=PASS
LIVE_VALIDATION_PASSED
injected_knowledge_patterns=['kp_0008', 'kp_0009', 'kp_0001']
```

Independent score:

```text
status=PASS
score=60/60
```

Knowledge quality:

```text
subject=docs/knowledge/opensku
status=PASS
score=60/60
record_count=45
reused_pattern_count=5
pattern_count=9
```

Promotion report:

```text
status=PASS
scanned_run_count=22
reuse_evidence_count=8
promoted_count=0
verified_reuse_pattern_count=3
```

Focused reuse regression after documentation sync:

```text
21 passed, 1 warning
```

Python compile check:

```text
PASS
```

Known residual risk:

```text
The current live run recovered after the evidence-checker specialist hit a recursion limit.
The lead agent completed the evidence work itself, wrote all 10 artifacts, called the writer and validator, called present_files, and passed external scoring.
Next hardening target: reduce evidence-checker prompt complexity or add a stricter specialist turn budget so this warning does not recur.
```

## Decision

Knowledge Reuse Injection is accepted for Phase 9 implementation level:

- knowledge patterns are read from `docs/knowledge/opensku/patterns.json`.
- selected patterns are injected into real live agent runs.
- run evidence records `injected_knowledge_patterns`.
- two real injected live runs passed validator and scoring.
- the current acceptance run uses the tightened selector and records only `kp_0008`, `kp_0009`, and `kp_0001`.
- reused patterns can be promoted from `draft` to `verified`.

## Next

1. Run an injected case in another stage, preferably `pre_launch_test` or `soft_launch`, to verify stage-specific selection outside idea-only.
2. Surface injected pattern IDs and maturity in the UI or final demo report.
3. Add a final release-candidate command that runs ingest -> promotion -> quality score in one gate.
