# 2026-06-27 - OpenSKU UI Productization

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: working tree, not committed
- Goal: advance Phase 8 so the UI communicates an adaptive launch loop, not only a decorative War Room.
- Scope: War Room model, first-viewport loop summary, loop artifact cards, mobile/desktop screenshots, and frontend validation.

## Thinking

The 10-run backend/eval acceptance proved the agent loop can produce staged artifacts. The UI still needed to expose that loop clearly:

- current launch stage.
- Go/Pivot/Hold/Kill/Scale decision.
- artifact readiness.
- private metric boundary.
- optional loop artifacts: `launch-state.json`, `promotion-replan.md`, `knowledge-deltas.json`.

This is important because the portfolio story should not look like a fixed "7-day package generator". The first viewport now makes the adaptive decision loop visible before the user scrolls into the game-like War Room details.

## Actions Executed

| Action | Command or File | Result |
|---|---|---|
| Added model red test | `frontend/tests/unit/components/workspace/ecom-launch/launch-crew-activity-model.test.ts` | Initially failed because `loopSnapshot` did not exist |
| Added loop snapshot model | `frontend/src/components/workspace/ecom-launch/launch-crew-activity-model.ts` | Extracts stage/decision from final response text, tracks core/loop artifacts, marks private metric boundary |
| Passed final response text into model | `frontend/src/components/workspace/ecom-launch/use-launch-crew-activity-model.ts` | War Room can derive `scale_iterate` and `Hold` from thread messages |
| Added War Room e2e red test | `frontend/tests/e2e/sidebar.spec.ts` | Initially failed because `[data-war-room-stage]` did not exist |
| Added first-viewport status strip | `frontend/src/components/workspace/ecom-launch/war-room-page.tsx` | Shows stage, decision, artifact readiness, and data boundary |
| Added loop artifact cards | `frontend/src/components/workspace/ecom-launch/war-room-page.tsx` | Dedicated entries for `launch-state.json`, `promotion-replan.md`, `knowledge-deltas.json` |
| Updated frontend assessment | `docs/ecom-launch/FRONTEND_ASSESSMENT.md` | Changed loop artifact UI from planned to built; noted remaining eval-score UI work |

## Screenshot Evidence

Stored under:

```text
docs/progress/runs/2026-06-27/phase-8-ui-productization/screenshots/
```

Files:

```text
opensku-war-room-desktop.png  1440 x 960
opensku-war-room-mobile.png   390 x 844
```

Visual checks:

- desktop first viewport shows `scale_iterate`, `Hold`, artifact readiness, and `GMV/CTR/CVR/ROI unavailable`.
- desktop War Room canvas renders nonblank and correctly framed.
- mobile first viewport shows stage, decision, artifact readiness, data boundary, and the canvas without incoherent overlap.
- loop artifact section is visible in desktop sidebar and covered by e2e selectors.

## Validation

Focused model red/green:

```bash
cd frontend
pnpm test -- tests/unit/components/workspace/ecom-launch/launch-crew-activity-model.test.ts
```

Observed:

```text
27 passed, 225 tests total in the filtered Vitest run
```

War Room e2e red/green:

```bash
cd frontend
pnpm test:e2e -- tests/e2e/sidebar.spec.ts -g "War Room syncs artifacts"
```

Observed after implementation:

```text
5 passed
```

Phase 8 focused verification:

```bash
cd frontend
pnpm typecheck
pnpm test -- tests/unit/components/workspace/ecom-launch
pnpm test:e2e -- tests/e2e/sidebar.spec.ts tests/e2e/agent-chat.spec.ts tests/e2e/artifact-preview.spec.ts
```

Observed:

```text
typecheck passed
27 test files passed
225 unit tests passed
14 e2e tests passed
```

## Decision

Phase 8 UI productization is accepted for the mock-thread/UI evidence level.

It should not be marked as final UI acceptance yet because the plan also asks for real live thread screenshot/video evidence. The remaining UI work is to surface eval score/evidence coverage in the product surface and capture a real-backend live UI run.

## Current Limitations

- Screenshot evidence uses a Playwright-routed mock thread, not a real live backend thread.
- The War Room currently displays artifact readiness and loop state, but not full eval score details.
- The full page still has a large component; further decomposition would improve maintainability.
