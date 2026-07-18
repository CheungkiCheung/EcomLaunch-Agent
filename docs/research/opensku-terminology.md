# OpenSKU Terminology

Date: 2026-06-27

Status: source-of-truth wording for docs, README, demo, and interview narrative

## Canonical Project Name

Use:

```text
OpenSKU
```

Expanded form:

```text
OpenSKU: evidence-governed adaptive SKU launch loop
```

Avoid making `deer-flow`, `harness`, or `War Room` the public project name. Those are implementation layers or UI surfaces.

## One-Sentence Description

Use:

```text
OpenSKU is a vertical agent system for SKU launch decisions: it diagnoses launch stage, generates evidence-backed artifacts, validates contracts, replans promotion from observed signals, and sediments reusable knowledge for later runs.
```

Short interview version:

```text
It is not a fixed seven-day launch pack. It is a stage-based SKU launch agent loop with evals and knowledge reuse.
```

## Core Terms

| Term | Use This Meaning | Avoid This Confusion |
|---|---|---|
| OpenSKU | the portfolio project and product concept | the base deer-flow harness |
| EcomLaunch Agent | the custom lead agent/runtime identity | the whole project |
| launch loop | diagnose, execute, validate, replan, learn | one-shot generation |
| launch stage | `idea_only`, `supplier_sample`, `pre_launch_test`, `soft_launch`, `scale_iterate` | a fixed day in a calendar |
| launch decision | `Go`, `Pivot`, `Hold`, `Kill`, `Scale` | generic recommendation |
| evidence-governed | claims must trace to public/uploaded/estimated/unavailable/assumption evidence | pretending public fixtures are private business metrics |
| artifact contract | required files and field rules checked by validators | a nice-to-have output list |
| live agent validation | real gateway/runtime/model/subagent/tool path | unit test, replay, or mocked model |
| OpenSKU-Bench | curated benchmark cases plus scoring | arbitrary prompt collection |
| knowledge delta | one source-linked learning extracted from a run | wiki page or generic note |
| reusable pattern | repeated and normalized knowledge from many deltas | a prompt tip |
| knowledge injection | selected patterns inserted into a later run context | dumping the whole knowledge base into prompt |
| maturity promotion | `draft -> verified -> proven` based on successful reuse | assuming generated reflections are true |
| data boundary | explicit limits of public fixtures and unavailable private metrics | a disclaimer only in docs |

## Terms To Avoid Or De-Emphasize

Avoid leading with:

```text
7-day package generator
LLM Wiki
RAG knowledge base
prompt workflow
agent demo
ecommerce content generator
```

These phrases make the project sound smaller than it is.

Use instead:

```text
adaptive launch loop
stage-based SKU decision system
artifact-contract validation
evidence-governed agent run
source-linked knowledge sedimentation
knowledge reuse injection
eval-driven agent delivery
```

## Naming Rules

### UI

Use:

```text
War Room
```

Only for the visual cockpit. Do not imply the War Room is the core value.

Correct:

```text
The War Room visualizes the launch loop and artifact readiness.
```

Incorrect:

```text
The War Room is the product.
```

### Harness

Use:

```text
harness
```

Only for the execution infrastructure that constrains and observes the agent.

Correct:

```text
The harness provides runtime orchestration, tool boundaries, and validation hooks.
```

Incorrect:

```text
The harness is the moat.
```

### Knowledge

Use:

```text
knowledge sedimentation
knowledge reuse
domain memory
```

Do not overuse:

```text
wiki
memory
reflection
```

Those terms are broad. OpenSKU's knowledge is narrower: typed, sourced, scored, and reused.

## Data Boundary Wording

Use:

```text
Public datasets and public signals are benchmark fixtures. They can support staged decision simulation and artifact validation, but they do not prove private merchant GMV, CTR, CVR, ROI, ad spend, sales, refund rate, repeat purchase rate, margin, live ranking, or verified uplift.
```

Short UI wording:

```text
GMV/CTR/CVR/ROI unavailable
```

Interview wording:

```text
I deliberately made the system refuse to invent private commerce metrics. Public evidence can support a launch hypothesis, not a verified business outcome.
```

## Phase 9 Wording

Use:

```text
Knowledge Reuse Injection
```

Definition:

```text
The runner selects a small, relevant set of source-linked OpenSKU patterns and injects them into a later live agent run. The run records which patterns were injected, and the scorer verifies that validation still passes.
```

This is the next major milestone because it turns knowledge from archive into execution memory.

## Resume Bullet Shape

Draft:

```text
Built OpenSKU, an evidence-governed SKU launch agent loop with 30 benchmark cases, 10 real live agent validations, artifact-contract validators, a scoring harness, and a source-linked knowledge sedimentation pipeline that prepares reusable patterns for later agent runs.
```

After knowledge injection is implemented:

```text
Built OpenSKU, an evidence-governed SKU launch agent loop that runs real multi-agent validations, scores required launch artifacts, extracts reusable domain patterns, and injects verified knowledge into later runs to reduce repeated failure modes such as unsupported private metric claims.
```
