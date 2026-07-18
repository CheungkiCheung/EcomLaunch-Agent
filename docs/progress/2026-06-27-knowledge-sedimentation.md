# 2026-06-27 - OpenSKU Knowledge Sedimentation

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: make knowledge deltas into an inspectable project asset, not just per-run artifacts.
- Scope: ingest script, quality scorer, tests, generated knowledge base, and docs.

## Thinking

The project should not stop at "a harness can run the agent." The more defensible story is that each run leaves behind reusable operational knowledge:

- decisions by stage.
- metric-boundary pitfalls.
- process guidance such as validator-before-present-files.
- source run IDs, source case IDs, and evidence IDs.

The ingester intentionally reads only accepted run evidence by default. Failed runs can be inspected manually, but they should not become reusable knowledge unless explicitly included.

## Actions Executed

| Action | Command or File | Result |
|---|---|---|
| Inspected live run deltas | `docs/progress/runs/2026-06-27/*/artifacts-manifest.json` -> output bundles | Each accepted run has `knowledge-deltas.json`; typical shape is `type`, `maturity`, `summary`, `source_case_id`, `evidence_ids` |
| Added ingest red test | `backend/tests/test_opensku_knowledge_ingest.py` | Initially failed because `scripts.opensku.ingest_knowledge_deltas` did not exist |
| Implemented ingester | `scripts/opensku/ingest_knowledge_deltas.py` | Reads PASS run dirs, follows `outputs_dir`, writes JSONL, patterns, report, README |
| Ran real ingest | `uv run --project backend python scripts/opensku/ingest_knowledge_deltas.py --runs docs/progress/runs --output docs/knowledge/opensku --min-records 20` | `status=PASS`, `accepted_run_count=13`, `record_count=39`, `pattern_count=9` |
| Added quality scorer red test | `backend/tests/test_opensku_knowledge_quality.py` | Initially failed because `evals.opensku.scorers` did not exist |
| Implemented deterministic scorer | `evals/opensku/scorers/knowledge_delta_quality.py` | Checks parseability, count, required fields, source links, private metric boundary, reuse patterns |
| Ran real quality score | `uv run --project backend python evals/opensku/scorers/knowledge_delta_quality.py --knowledge docs/knowledge/opensku --min-records 20 --min-reused-patterns 5` | `status=PASS`, `score=60/60` |
| Documented commands | `evals/opensku/README.md` | Added knowledge sedimentation section |

## Generated Knowledge Base

Directory:

```text
docs/knowledge/opensku/
```

Files:

```text
README.md
ingest-report.json
knowledge-deltas.jsonl
patterns.json
```

Current snapshot:

```text
accepted_run_count=13
record_count=39
pattern_count=9
reused_pattern_count=5
```

Record distribution:

```text
decision: 13
pitfall: 13
process: 13
maturity: draft 39
unique_runs: 13
unique_cases: 13
```

Most reused patterns:

```text
Do not convert public fixtures or public review language into private commerce metrics.  occurrence_count=13
Use a runtime artifact writer plus validator for benchmark runs so long HTML/CSV payloads do not depend on a giant model tool call.  occurrence_count=13
```

## Validation

Focused tests:

```bash
cd backend
uv run pytest tests/test_opensku_knowledge_ingest.py tests/test_opensku_knowledge_quality.py -q
```

Observed:

```text
3 passed, 1 warning
```

Quality scorer:

```text
subject=docs/knowledge/opensku
status=PASS
score=60/60
parseability: PASS 10/10
record_count: PASS 10/10
required_fields: PASS 10/10
source_links: PASS 10/10
private_metric_boundary: PASS 10/10
reuse_patterns: PASS 10/10
```

## Data Boundary

The knowledge base is generated from public benchmark fixture runs and public-fixture-as-uploaded simulations. It does not claim private merchant telemetry. The scorer blocks private metric mentions unless they are framed as unavailable or future data to collect.

## Decision

Phase 9 has a first accepted implementation: knowledge deltas are now durable, source-linked, and scored.

Remaining work for a stronger knowledge moat:

- mature repeated deltas from `draft` to `verified` only after later runs explicitly reuse them.
- make the agent read `docs/knowledge/opensku/patterns.json` before future benchmark runs.
- surface top reusable patterns in the UI or demo guide.
