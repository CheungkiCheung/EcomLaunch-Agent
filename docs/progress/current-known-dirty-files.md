# Current Known Dirty Files

Date: 2026-06-27

Branch: `feature/ecom-launch-cockpit`

Commit: `c85a39b`

Purpose: Phase 0 baseline record. This file separates current worktree changes so later phases do not accidentally treat pre-existing work as new evidence.

## Summary

Current worktree is intentionally dirty. The dirty set falls into three groups:

1. OpenSKU positioning and planning work.
2. Existing War Room visual/animation work.
3. New plan/progress files for the complete execution plan.

Do not revert unrelated dirty files. Work with them if they affect the OpenSKU plan; otherwise leave them alone.

## Group A: OpenSKU Positioning And Planning Changes

These files are aligned with the OpenSKU documentation cleanup and complete execution plan:

```text
AGENTS.md
Install.md
README.md
README_fr.md
README_ja.md
README_ru.md
README_zh.md
agents/ecom-launch/SOUL.md
backend/README.md
backend/tests/test_ecom_launch_contract.py
docs/ecom-launch/FRONTEND_ASSESSMENT.md
docs/ecom-launch/README.md
docs/ecom-launch/USER_MANUAL.md
docs/ecom-launch/manual-run-prompt.md
docs/plans/ecom-launch-agent-spec.md
docs/plans/opensku-complete-execution-plan.md
docs/progress/README.md
docs/progress/2026-06-27-complete-plan-baseline.md
docs/progress/2026-06-27-phase-0-baseline-audit.md
docs/progress/current-known-dirty-files.md
docs/superpowers/plans/2026-06-17-growth-experiment-engine.md
frontend/README.md
frontend/package.json
frontend/src/app/(auth)/login/page.tsx
frontend/src/app/(auth)/setup/page.tsx
frontend/src/app/layout.tsx
frontend/src/core/agents/api.ts
frontend/src/core/i18n/locales/en-US.ts
frontend/src/core/i18n/locales/zh-CN.ts
skills/custom/ecom-launch/SKILL.md
```

## Group B: Existing War Room Visual / UI Asset Work

These files are dirty but are not part of Phase 0. They should not be reverted during data/eval planning.

```text
frontend/public/images/ecom-launch/war-room/agents/asset-studio/idle.png
frontend/public/images/ecom-launch/war-room/agents/asset-studio/walk-down.png
frontend/public/images/ecom-launch/war-room/agents/asset-studio/walk-left.png
frontend/public/images/ecom-launch/war-room/agents/asset-studio/walk-right.png
frontend/public/images/ecom-launch/war-room/agents/asset-studio/walk-up.png
frontend/public/images/ecom-launch/war-room/agents/asset-studio/work.png
frontend/public/images/ecom-launch/war-room/agents/evidence-checker/idle.png
frontend/public/images/ecom-launch/war-room/agents/evidence-checker/walk-down.png
frontend/public/images/ecom-launch/war-room/agents/evidence-checker/walk-left.png
frontend/public/images/ecom-launch/war-room/agents/evidence-checker/walk-right.png
frontend/public/images/ecom-launch/war-room/agents/evidence-checker/walk-up.png
frontend/public/images/ecom-launch/war-room/agents/evidence-checker/work.png
frontend/public/images/ecom-launch/war-room/agents/growth-analyst/idle.png
frontend/public/images/ecom-launch/war-room/agents/growth-analyst/walk-down.png
frontend/public/images/ecom-launch/war-room/agents/growth-analyst/walk-left.png
frontend/public/images/ecom-launch/war-room/agents/growth-analyst/walk-right.png
frontend/public/images/ecom-launch/war-room/agents/growth-analyst/walk-up.png
frontend/public/images/ecom-launch/war-room/agents/growth-analyst/work.png
frontend/public/images/ecom-launch/war-room/agents/launch-director/alert.png
frontend/public/images/ecom-launch/war-room/agents/launch-director/idle.png
frontend/public/images/ecom-launch/war-room/agents/launch-director/talk.png
frontend/public/images/ecom-launch/war-room/agents/launch-director/work.png
frontend/public/images/ecom-launch/war-room/agents/market-voc-researcher/idle.png
frontend/public/images/ecom-launch/war-room/agents/market-voc-researcher/walk-down.png
frontend/public/images/ecom-launch/war-room/agents/market-voc-researcher/walk-left.png
frontend/public/images/ecom-launch/war-room/agents/market-voc-researcher/walk-right.png
frontend/public/images/ecom-launch/war-room/agents/market-voc-researcher/walk-up.png
frontend/public/images/ecom-launch/war-room/agents/market-voc-researcher/work.png
frontend/public/images/ecom-launch/war-room/agents/offer-architect/idle.png
frontend/public/images/ecom-launch/war-room/agents/offer-architect/walk-down.png
frontend/public/images/ecom-launch/war-room/agents/offer-architect/walk-left.png
frontend/public/images/ecom-launch/war-room/agents/offer-architect/walk-right.png
frontend/public/images/ecom-launch/war-room/agents/offer-architect/walk-up.png
frontend/public/images/ecom-launch/war-room/agents/offer-architect/work.png
frontend/public/images/ecom-launch/war-room/props/artifact-conveyor.png
frontend/public/images/ecom-launch/war-room/props/big-screen.png
frontend/public/images/ecom-launch/war-room/props/command-console.png
frontend/public/images/ecom-launch/war-room/props/whiteboard.png
frontend/public/images/ecom-launch/war-room/props/workstation.png
frontend/public/images/ecom-launch/war-room/room/background.png
frontend/scripts/process-ecom-war-room-image2-assets.py
frontend/src/components/workspace/ecom-launch/war-room-assets.ts
frontend/src/components/workspace/ecom-launch/war-room-canvas-stage.tsx
frontend/src/components/workspace/ecom-launch/war-room-motion.ts
frontend/src/components/workspace/ecom-launch/war-room-page.tsx
frontend/tests/unit/components/workspace/ecom-launch/war-room-assets.test.ts
frontend/tests/unit/components/workspace/ecom-launch/war-room-motion.test.ts
```

## Group C: New Untracked War Room Assets

These assets existed in the worktree at Phase 0. They are not part of the data/eval plan.

```text
frontend/public/images/ecom-launch/war-room/artifacts/
frontend/public/images/ecom-launch/war-room/props/coffee-station.png
```

The `artifacts/` directory currently contains:

```text
analytics-folder.png
approval-stamp.png
creative-thumbnail.png
evidence-checklist.png
items-sheet.png
launch-calendar.png
package.png
product-card.png
research-report.png
```

## Phase 0 Decision

Proceed with data/eval planning from this dirty baseline. Do not attempt cleanup or revert before Phase 1 unless a dirty file directly blocks implementation or validation.

