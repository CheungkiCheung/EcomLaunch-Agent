# ADR 0001: OpenSKU Is Not A Fixed Seven-Day Launch Pack

Date: 2026-06-27

Status: accepted

## Context

The project originally risked being interpreted as a generator for a fixed seven-day launch package. That framing is too small and does not match real ecommerce launch work. Many SKU situations do not need the same calendar. Some need idea validation, some need supplier/sample claim checks, some need pre-launch search-fit testing, some need soft-launch diagnosis, and some need scale or hold decisions.

The user also raised the product question directly: real companies do not always "launch for seven days"; they adapt based on data, product availability, channel context, and observed feedback.

## Decision

OpenSKU will be framed as:

```text
an evidence-governed adaptive SKU launch loop
```

The core loop is:

```text
diagnose stage
-> collect or accept evidence
-> generate required launch artifacts
-> validate artifact contracts
-> decide Go/Pivot/Hold/Kill/Scale
-> replan promotion or next experiment
-> capture knowledge deltas
```

`launch-calendar.csv` remains a required artifact, but it is an experiment calendar with validation signals and decision rules. It is not the product's central promise and it is not always seven days.

## Consequences

Positive:

- The project better matches realistic SKU launch work.
- It becomes easier to justify five benchmark stages.
- Promotion replanning and `launch-state.json` become core, not optional decoration.
- Interview framing becomes more credible than a content generator.

Tradeoff:

- The project is harder to explain in one sentence.
- More docs must consistently use stage/decision-loop language.

## Implementation Notes

Docs, prompts, UI, and demo scripts should avoid leading with "seven-day package." Use "next-stage launch decision pack" or "adaptive validation plan" instead.
