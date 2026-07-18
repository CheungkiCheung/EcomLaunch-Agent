# OpenSKU Knowledge Base

This directory is generated from accepted OpenSKU live run artifacts.

The records come from `knowledge-deltas.json` files produced by the agent and
are tied back to source run directories, run IDs, case IDs, and evidence IDs.
Public benchmark fixtures remain benchmark evidence; this knowledge base does
not claim private merchant GMV, CTR, CVR, ROI, ad spend, sales, refund, repeat
purchase, or verified uplift.

This is execution memory, not a general-purpose wiki. A pattern is only useful
when it can be traced to an accepted run, selected into a later run, and promoted
after that later run passes the artifact and decision gates.

## Current Snapshot

```text
status=PASS
accepted_run_count=21
record_count=63
pattern_count=13
reuse_evidence_count=31
promoted_count=4
verified_reuse_pattern_count=4
quality_score=60/60
```

Commands used for the current snapshot:

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

## Files

```text
knowledge-deltas.jsonl
patterns.json
ingest-report.json
promotion-report.json
```

## Maturity Boundary

- `draft`: extracted from accepted run output, source-linked, but not yet reused.
- `verified`: injected into a later live run that passed validation.
- `proven`: reserved for repeated cross-stage reuse. The current snapshot has
  verified patterns, not broad production proof.

Knowledge selection intentionally injects only a small set of relevant patterns
per run. It does not paste the whole knowledge base into the prompt.
