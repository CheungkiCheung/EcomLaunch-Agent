# 2026-06-27 - OpenSKU Agent Loop Research Checkpoint

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: calibrate OpenSKU against high-quality agent engineering references before implementing knowledge reuse injection.
- Scope: local PDF review, external source review, terminology decision, ADRs, and Phase 9 plan update.

## Thinking

The project has already moved beyond a simple launch-pack generator: it has benchmark cases, real live runs, artifact validators, scoring, UI evidence, and first-pass knowledge sedimentation.

The remaining risk is conceptual drift. If the next work is described as an LLM Wiki or normal RAG memory, the project sounds smaller than the engineering actually supports. The research checkpoint therefore focused on deciding what to adopt and what to reject:

- adopt eval-driven agent delivery: input, execution, trace/artifacts, checks, comparable scores.
- adopt knowledge as a source-linked and governed execution memory.
- adopt progressive disclosure and query budgets for knowledge injection.
- reject fixed seven-day launch framing.
- reject dumping the whole knowledge base into the prompt.
- reject treating generated run reflections as truth before later successful reuse.

## Actions Executed

| Action | Command / File | Result |
|---|---|---|
| Read project instructions | `AGENTS.md`, `deer-flow/AGENTS.md` | Confirmed OpenSKU identity, logging, TDD/verification expectations, and public metric boundaries |
| Read agent-reach skill | `/Users/zhangqixiang/.agents/skills/agent-reach/SKILL.md` | Confirmed research/web routing expectations |
| Read PDF skill | `/Users/zhangqixiang/.codex/plugins/cache/openai-primary-runtime/pdf/26.623.12021/skills/pdf/SKILL.md` | Confirmed PDF extraction/rendering approach |
| Inspected PDFs | `pdfinfo` on the two desktop PDFs | Harness PDF: 16 pages. Eval PDF: 39 pages. Both unencrypted A4 Chrome PDFs |
| Rendered first pages | `pdftoppm -png -f 1 -singlefile ...` | Saved visual checks under `tmp/pdfs/` |
| Extracted PDF text | bundled Python + `pypdf` to `tmp/pdfs/harness.txt` and `tmp/pdfs/eval.txt` | Harness text: about 16k chars. Eval text: about 26k chars |
| Scanned source concepts | `rg` over extracted text | Identified knowledge layers, maturity, query budget, eval scorer layers, trace/artifact requirements, stability scoring |
| Reviewed external references | OpenAI evals, Anthropic agent engineering, 12 Factor Agents, LangGraph docs, Shopify launch guidance | Used as calibration for evals, long-running agents, durable state, human gates, and adaptive launch framing |
| Added research note | `docs/research/opensku-agent-loop-research-notes.md` | Captures source synthesis and next implementation target |
| Added terminology doc | `docs/research/opensku-terminology.md` | Defines canonical wording for OpenSKU, launch loop, knowledge delta, injection, maturity, and data boundary |
| Added ADR 0001 | `docs/adr/0001-opensku-is-not-seven-day-pack.md` | Accepts adaptive stage-based launch loop framing |
| Added ADR 0002 | `docs/adr/0002-knowledge-is-execution-memory-not-wiki.md` | Accepts execution-memory framing over LLM Wiki framing |
| Added ADR 0003 | `docs/adr/0003-live-eval-contracts-are-release-gates.md` | Accepts real live validation as milestone gate for agent behavior |
| Updated execution plan | `docs/plans/opensku-complete-execution-plan.md` | Phase 9 now requires knowledge injection, run evidence, and maturity promotion |
| Cleaned current 7-day remnants | `docs/ecom-launch/subagents.ecom-launch.yaml`, `docs/ecom-launch/demo-brief.portable-coffee-tumbler.json` | Replaced fixed 7-day wording with adaptive validation wording |

## Evidence

Created:

```text
docs/research/opensku-agent-loop-research-notes.md
docs/research/opensku-terminology.md
docs/adr/0001-opensku-is-not-seven-day-pack.md
docs/adr/0002-knowledge-is-execution-memory-not-wiki.md
docs/adr/0003-live-eval-contracts-are-release-gates.md
docs/progress/2026-06-27-agent-loop-research-checkpoint.md
```

Updated:

```text
docs/plans/opensku-complete-execution-plan.md
docs/ecom-launch/subagents.ecom-launch.yaml
docs/ecom-launch/demo-brief.portable-coffee-tumbler.json
```

Local PDF evidence:

```text
tmp/pdfs/harness-page1.png
tmp/pdfs/eval-page1.png
tmp/pdfs/harness.txt
tmp/pdfs/eval.txt
```

Reference URLs:

```text
https://platform.openai.com/docs/guides/evals
https://www.anthropic.com/engineering/building-effective-agents
https://github.com/humanlayer/12-factor-agents
https://docs.langchain.com/oss/python/langgraph/overview
https://www.shopify.com/blog/product-launch
```

## Validation

Validated concept alignment against existing project state:

- OpenSKU already has 30 benchmark cases.
- OpenSKU already has 10 accepted live runs and `PASS 420/420` scoring.
- OpenSKU already has artifact validators and knowledge ingest.
- The next missing loop is knowledge reuse injection and maturity promotion.

Validation commands run:

```bash
git diff --check
rg -n "LLM Wiki|7-day|seven-day|七天|七日|7 日|7天" README.md docs agents skills evals --glob '!docs/progress/runs/**' --glob '!docs/compose/**' --glob '!docs/superpowers/**'
```

Observed:

```text
git diff --check: PASS
terminology scan: current fixed 7-day wording cleaned from the active subagent prompt and demo brief.
remaining matches are negative framing, warranty-policy examples, adaptive-cadence guidance, ADR/research text, or historical progress logs.
```

## Decision

Proceed to implement Knowledge Reuse Injection next.

The next milestone should not add more generic research or more benchmark cases. It should make `docs/knowledge/opensku/patterns.json` affect a real later live run, with injected pattern evidence recorded and validator/scoring still passing.

## Next

1. Add a knowledge context selector for `patterns.json`.
2. Add `--knowledge-dir docs/knowledge/opensku` to the live runner.
3. Inject selected patterns into the live prompt with a 3 to 5 pattern budget.
4. Persist `injected_knowledge_patterns` in run evidence.
5. Add tests for selection, prompt formatting, and run metadata.
6. Run one real live case with injection enabled.
7. Promote one successfully reused pattern from `draft` to `verified`.
