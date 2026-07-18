# OpenSKU Agent Loop Research Notes

Date: 2026-06-27

Status: research checkpoint for the OpenSKU completion plan

## Purpose

This note calibrates OpenSKU against high-quality agent engineering references before the next implementation step. The goal is not to collect generic RAG or prompt-engineering ideas. The goal is to decide which concepts should shape OpenSKU's remaining work:

- agent eval and artifact contracts.
- long-running launch loops.
- knowledge sedimentation.
- knowledge reuse injection.
- knowledge maturity promotion.

## Sources Reviewed

Local source documents:

- `/Users/zhangqixiang/Desktop/Harness不是目的，知识才是护城河 —— 一个AI工程交付团队的知识沉淀实践.pdf`
- `/Users/zhangqixiang/Desktop/AI Agent & Skill 测评方案及落地实践.pdf`

External references:

- OpenAI evals guide: https://platform.openai.com/docs/guides/evals
- Anthropic, Building Effective Agents: https://www.anthropic.com/engineering/building-effective-agents
- HumanLayer, 12 Factor Agents: https://github.com/humanlayer/12-factor-agents
- LangGraph overview and docs: https://docs.langchain.com/oss/python/langgraph/overview
- Shopify product launch guide: https://www.shopify.com/blog/product-launch

## Research Synthesis

### 1. Harness is infrastructure, not the product moat

The harness article's strongest implication for OpenSKU is that workflow complexity is replaceable, while domain knowledge is cumulative.

For OpenSKU, this means:

- The LangGraph/deer-flow harness should be presented as the execution substrate.
- The defensible project value is not "we can orchestrate subagents."
- The defensible value is "each SKU launch run produces source-linked knowledge that can constrain later runs."

Adopt:

- `INIT -> EXECUTE -> VALIDATE -> ARCHIVE -> REUSE` as the knowledge-flow frame.
- File-based state and source-linked artifacts because they are visible, versionable, and inspectable.
- Knowledge maturity states: `draft -> verified -> proven`, plus later `deprecated` for OpenSKU-specific governance.

Do not adopt blindly:

- A generic cross-team knowledge repository yet. OpenSKU is a portfolio project, so project-level `docs/knowledge/opensku/` is enough for now.
- Unlimited knowledge injection. The article explicitly warns about context bloat, so OpenSKU needs a retrieval budget.

### 2. OpenSKU should not be described as an LLM Wiki

LLM Wiki is a useful analogy for ingest/query/lint, but it is too broad and too static for this project.

OpenSKU should be described as:

```text
an evidence-governed domain memory loop for SKU launch agents
```

The difference:

| Concept | LLM Wiki | OpenSKU |
|---|---|---|
| Main consumer | human asking questions | launch agent making decisions |
| Knowledge unit | page or chunk | decision, pitfall, process, model, guideline |
| Source | documents and notes | accepted agent runs, artifacts, validators, benchmark cases |
| Validation | usually weak or manual | artifact validators, scoring reports, live run acceptance |
| Reuse | retrieval for answer generation | prompt/tool context injection for next launch run |
| Lifecycle | ingest/query/lint | ingest/query/inject/cite/promote/decay |

This is the most important positioning decision. If a recruiter hears "LLM Wiki," the project sounds like a RAG knowledge base. If they hear "evidence-governed domain memory loop," the project sounds like agent infrastructure for reliable delivery.

### 3. Agent eval should be trace plus artifact plus score

The eval PDF maps directly to the OpenSKU implementation:

```text
Agent input -> execution -> trace and artifacts -> checks -> comparable score
```

OpenSKU already has a strong subset:

- curated benchmark cases.
- real live agent runs.
- required artifact contract.
- deterministic validators.
- aggregate score reports.
- run logs under `docs/progress/runs/`.

The next improvement is not more benchmark cases. The next improvement is trace-level knowledge reuse evidence:

- which knowledge patterns were injected.
- where they influenced the prompt or run context.
- whether the final artifacts cite the injected pattern IDs.
- whether validators and scoring still pass after injection.

### 4. Scorer layering should stay conservative

The eval PDF recommends using deterministic scoring first, rubric scoring second, human review for calibration and high-risk cases. OpenSKU should keep that order.

Current fit:

- Deterministic scorers are appropriate for file presence, JSON/CSV parseability, required fields, evidence references, forbidden private metric claims, and artifact completeness.
- Rubric scoring can be added later for positioning quality, experiment quality, copy quality, or launch reasoning.
- Human review belongs in final demo acceptance and failed-run diagnosis, not as the primary gate.

Decision:

```text
OpenSKU Phase 9/10 should not introduce an LLM judge as the main release gate.
```

The stronger portfolio story is that OpenSKU knows which parts can be checked objectively and uses the model only where semantic judgment is truly needed.

### 5. Long-running agents need durable state and explicit human gates

Anthropic's agent guidance and LangGraph's design both support a practical lesson: longer agent tasks need durable state, tool boundaries, and human-visible progress.

OpenSKU should express long-running launch work as a loop:

```text
diagnose stage
-> gather evidence
-> generate artifacts
-> validate contracts
-> decide Go/Pivot/Hold/Kill/Scale
-> replan promotion
-> archive knowledge deltas
-> reuse validated patterns
```

This matters because a real SKU launch is not a fixed seven-day content pack. It is a stage-based operating loop. Some cases need idea validation, some need supplier claim readiness, some need search-fit testing, some need soft-launch signal diagnosis, and some need scale/reallocation decisions.

### 6. Product launch planning should be adaptive, not calendar-first

The Shopify launch reference is useful mainly as a reality check: product launch work includes market research, positioning, asset preparation, channel execution, and post-launch performance review. That supports the user's intuition that "seven days" is not universally real.

OpenSKU should therefore avoid saying:

```text
generate a 7-day launch package
```

It should say:

```text
generate the next-stage launch decision pack and adaptive validation plan
```

`launch-calendar.csv` can still exist, but it should be framed as an experiment calendar with decision rules, not as a fixed promotional promise.

## Adopted Design Principles

### Principle 1: Knowledge must be source-linked

Every reusable knowledge record must keep:

- source run ID.
- source case ID.
- evidence IDs.
- artifact paths or manifest links.
- maturity.

Without source links, knowledge is just model-generated advice.

### Principle 2: Knowledge must be typed

Use OpenSKU's current types:

- `decision`
- `guideline`
- `pitfall`
- `process`
- `model`

Add one implementation detail:

- Each pattern should also have `stage`, `category`, `tags`, and `applies_when` so the runner can choose patterns without dumping the whole knowledge base into context.

### Principle 3: Knowledge injection must be budgeted

For the next implementation:

```text
max injected patterns per run: 3 to 5
selection priority: stage match > risk tag match > occurrence count > maturity
```

This follows progressive disclosure. The runner should not paste the whole knowledge base into the prompt.

### Principle 4: Reuse must be observable

A run with injected knowledge must record:

```json
{
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

The final artifacts should also carry either explicit pattern references or enough run metadata for the scorer to verify reuse. Otherwise "the agent used memory" is not auditable.

### Principle 5: Maturity promotion requires later successful reuse

The current knowledge base correctly keeps all records at `draft`. That is honest.

The next rule should be:

```text
draft -> verified:
  pattern was injected into a later live run and that run passed validators/scoring.

verified -> proven:
  pattern was reused successfully across at least two stages or three accepted live runs.

any -> deprecated:
  pattern conflicts with a newer accepted run, stale data boundary, or current project contract.
```

This prevents OpenSKU from treating one run's reflection as truth.

## Implications For The Current Project

### What is already aligned

- 30-case benchmark suite.
- 10 accepted live runs.
- artifact writer and artifact validator.
- forbidden private metrics boundary.
- scoring report with `PASS 420/420`.
- knowledge ingest and quality scoring.
- progress logs and run directories.

### What is still incomplete

- `patterns.json` is not yet injected into future agent runs.
- run logs do not yet record `injected_knowledge_patterns`.
- patterns do not yet advance from `draft` to `verified/proven`.
- UI does not yet show knowledge reuse or eval score as first-class evidence.
- final demo package does not yet narrate the knowledge loop.

## Next Implementation Target

The next milestone should be:

```text
Knowledge Reuse Injection
```

Scope:

- Add a knowledge context selector that reads `docs/knowledge/opensku/patterns.json`.
- Select a small relevant pattern set by stage, category, tags, occurrence count, and maturity.
- Inject the selected patterns into `run_live_agent_validation.py` prompts.
- Persist selected patterns in the live run metadata.
- Add deterministic tests that verify prompt construction and run evidence.
- Run at least one real live case with injection enabled.

Acceptance:

- Unit tests prove selection and prompt formatting.
- Existing live-run tests prove the new metadata contract.
- One real live run writes `injected_knowledge_patterns`.
- The run still passes artifact validation and scoring.
- A progress log explains whether injected knowledge changed or constrained the output.

## Interview Framing

Use this phrasing:

```text
OpenSKU is not a seven-day launch-pack generator. It is an evidence-governed SKU launch loop. The system runs real agent tasks, validates required launch artifacts, scores them, extracts source-linked knowledge deltas, mines reusable patterns, and then injects those patterns into later runs so the agent can reuse verified domain experience.
```

Avoid this phrasing:

```text
It is an LLM Wiki for ecommerce.
```

That makes the project sound like a generic RAG app and hides the actual engineering work.
