# 2026-06-27 - Complete Plan Baseline

## Context

- Branch: `feature/ecom-launch-cockpit`
- Goal: create a complete execution plan for turning OpenSKU into a real data-backed, eval-backed, live-agent-validated project.
- Scope: planning only. No runtime implementation in this log.

## Thinking

The current project has a clearer product narrative after the documentation cleanup: OpenSKU is an adaptive SKU launch loop, and EcomLaunch is the internal agent/skill workflow. The remaining strategic gap is proof.

The project should not pass by saying "the UI renders" or "a contract test checks strings." The important proof is whether the real agent can handle real ecommerce-like context, generate artifacts, avoid fake metrics, replan promotion based on data, and leave reusable knowledge behind.

I chose a complete plan with three validation layers:

- fast tests for regression,
- replay tests for stable backend/frontend protocol coverage,
- live agent runs for product truth.

The live layer is mandatory. If no real model/API key/data is available, the related milestone is blocked rather than downgraded to mock validation.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Read current product README | `README.md` | Confirmed OpenSKU positioning and current roadmap. |
| 2026-06-27 | Read agent spec | `docs/plans/ecom-launch-agent-spec.md` | Confirmed adaptive loop contract and required artifacts. |
| 2026-06-27 | Read MVP docs | `docs/ecom-launch/README.md` | Confirmed current manual MVP acceptance criteria. |
| 2026-06-27 | Read skill contract | `skills/custom/ecom-launch/SKILL.md` | Confirmed required roles, forbidden metrics, and artifact expectations. |
| 2026-06-27 | Inspected real backend/replay tests | `frontend/tests/e2e-real-backend/`, `backend/tests/test_replay_golden.py` | Confirmed existing replay and real-backend test patterns that the plan can extend. |
| 2026-06-27 | Verified open dataset references | web search | Confirmed public sources for Amazon Reviews 2023, Olist, ESCI, WANDS, MAVE, Taobao behavior data, and TAOBAO-MM. |
| 2026-06-27 | Created complete execution plan | `docs/plans/opensku-complete-execution-plan.md` | Added full project phases, acceptance criteria, validation tiers, and logging protocol. |
| 2026-06-27 | Created progress log protocol | `docs/progress/README.md` | Added required milestone/run log template. |

## Evidence

Created files:

```text
docs/plans/opensku-complete-execution-plan.md
docs/progress/README.md
docs/progress/2026-06-27-complete-plan-baseline.md
```

Public dataset sources verified during planning:

- Amazon Reviews 2023: https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
- Olist Brazilian E-Commerce Public Dataset: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- Amazon ESCI Shopping Queries Dataset: https://github.com/amazon-science/esci-data
- Wayfair WANDS: https://github.com/wayfair/WANDS
- MAVE: https://ar5iv.labs.arxiv.org/html/2112.08663
- Taobao User Behavior: https://tianchi.aliyun.com/dataset/649?lang=en-us
- TAOBAO-MM: https://taobao-mm.github.io/

## Validation

This was a planning milestone, so no implementation tests were required.

Validation performed:

- checked existing OpenSKU docs for current source of truth.
- checked current runtime/replay test patterns.
- checked public data source availability.
- wrote explicit future validation commands into the plan.

Not tested:

- no live agent call was executed in this planning step.
- no dataset download was executed.
- no eval harness exists yet.

## Decision

Proceed with the full execution plan. The next goal-mode run should start with Phase 0, not jump directly to UI or eval code.

## Next

1. Run Phase 0 baseline audit.
2. Create `docs/progress/current-known-dirty-files.md`.
3. Start Phase 1 data map and dataset license/usage docs.
4. Only after data docs are written, implement the case schema and validators.

