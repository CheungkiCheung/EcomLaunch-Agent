# 2026-06-27 - OpenSKU Knowledge Reuse Injection Plan

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: turn OpenSKU knowledge from a generated archive into execution memory that constrains later live agent runs.
- Scope: knowledge pattern selection, prompt injection, live-run evidence metadata, tests, and real-run acceptance path.

## Thinking

The project already has accepted live runs, artifact validators, scoring, and `docs/knowledge/opensku/patterns.json`. The remaining gap is that future runs do not yet consume those patterns. Without reuse, the knowledge base is inspectable but not yet a closed loop.

The implementation will keep the design conservative:

- inject only a small relevant pattern set, not the whole knowledge base.
- prefer deterministic selection before any semantic retrieval.
- record injected pattern IDs in run evidence.
- keep final artifact lists filenames-only to avoid repeating the previous count-hallucination failure.
- treat maturity promotion as a later successful-reuse event, not as a generated claim.

## Execution Plan

| Step | Action | Acceptance |
|---|---|---|
| 1 | Add failing tests for knowledge pattern loading, selection, prompt formatting, and manifest evidence | Tests fail before implementation because `knowledge_context` and runner support do not exist |
| 2 | Implement `evals/opensku/knowledge_context.py` | Loads `patterns.json`, selects 3-5 relevant patterns, formats a bounded prompt section |
| 3 | Extend live runner CLI | `run_live_agent_validation.py` accepts `--knowledge-dir` and can pass selected patterns into `build_live_prompt` |
| 4 | Add prompt injection | Prompt includes a clear `Relevant OpenSKU reusable knowledge` section with pattern IDs and statements |
| 5 | Add evidence metadata | `artifacts-manifest.json` records `injected_knowledge_patterns` and `knowledge_dir` |
| 6 | Run focused tests | `backend/tests/test_opensku_knowledge_context.py` and `backend/tests/test_opensku_live_runner.py` pass |
| 7 | Run one real live validation with injection | A run under `docs/progress/runs/<date>/...` records injected patterns and passes validators/scoring |
| 8 | Update progress log | Log records commands, evidence, results, and whether any pattern can be promoted |

## Acceptance Standard

This milestone is accepted only when all are true:

- `docs/knowledge/opensku/patterns.json` is read by the runner through `--knowledge-dir`.
- selection is bounded to 3-5 patterns.
- `kp_0008` or an equivalent private-metric-boundary pattern is selected for benchmark fixture runs.
- prompt injection includes pattern IDs and statements.
- run evidence records:

```json
{
  "knowledge_dir": "docs/knowledge/opensku",
  "injected_knowledge_patterns": [
    {
      "id": "kp_0008",
      "type": "pitfall",
      "maturity": "draft",
      "occurrence_count": 13,
      "statement": "Do not convert public fixtures or public review language into private commerce metrics."
    }
  ]
}
```

- existing final-response contract remains enforced: final artifact list filenames only.
- focused tests pass.
- at least one real live injected run is executed before marking Phase 9 reuse complete.

## Non-Goals

- Do not add vector search yet.
- Do not add an LLM judge as the primary gate.
- Do not promote every generated delta automatically.
- Do not claim private commerce uplift from public fixtures.

## Next

Start TDD implementation with `backend/tests/test_opensku_knowledge_context.py` and focused additions to `backend/tests/test_opensku_live_runner.py`.
