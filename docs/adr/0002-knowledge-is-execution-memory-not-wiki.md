# ADR 0002: Knowledge Is Execution Memory, Not A Wiki

Date: 2026-06-27

Status: accepted

## Context

The project now has `docs/knowledge/opensku/` with generated `knowledge-deltas.jsonl`, `patterns.json`, and `ingest-report.json`. This creates a risk that the project gets described as an LLM Wiki or a normal RAG knowledge base.

That framing is incomplete. The purpose of OpenSKU knowledge is not just to answer human questions. The purpose is to constrain and improve later SKU launch agent runs.

## Decision

OpenSKU knowledge will be treated as execution memory.

Knowledge records must be:

- typed: `decision`, `guideline`, `pitfall`, `process`, or `model`.
- sourced: linked to case ID, run ID, and evidence IDs.
- scored: checked by deterministic or quality scorers.
- budgeted: selected in small relevant sets, not dumped wholesale.
- reusable: injected into later agent runs.
- governed: promoted or deprecated based on later evidence.

## Consequences

Positive:

- The project differentiates from generic RAG.
- Knowledge becomes part of the agent reliability loop.
- Failed or unsupported claims can become reusable prevention patterns.
- The story aligns with the "harness is not the moat, knowledge is" thesis.

Tradeoff:

- The implementation needs more metadata than a simple markdown wiki.
- Future live runs must record `injected_knowledge_patterns`.

## Implementation Notes

Next milestone:

```text
Knowledge Reuse Injection
```

The runner should read `docs/knowledge/opensku/patterns.json`, select 3 to 5 relevant patterns, inject them into the prompt/context, and write the selected pattern metadata into the run evidence.

The final response contract should remain filenames-only for artifact lists. Knowledge references should be stored in run metadata or dedicated artifacts, not guessed in the final prose.
