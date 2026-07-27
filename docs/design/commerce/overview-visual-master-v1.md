# Commerce Overview Visual Master v1

## Status

- Generated with the built-in `imagegen` tool.
- Superseded as a shared visual master after user review on 2026-07-20.
- The user selected a lighter Codex Desktop-inspired, Chinese-first shell direction in `master-shell-visual-v2.png`.
- This image remains a historical layout experiment only and must not be used as the React visual baseline.
- Raster reference: `docs/design/commerce/mockups/overview-visual-master-v1.png`.

## Page goal

Establish the shared visual system for the Case-first Commerce Workspace:

- Case and Domain Event data are primary.
- Chat is a secondary command surface.
- Agent Runtime is inspectable beside business state.
- The layout stays compact, restrained, and implementable with the existing Next.js stack.

## Evidence state represented

The business content is limited to the current frozen public fixtures and implemented runtime contracts:

- six uploaded tables in `GC-FULFILLMENT-001`;
- three Gold Cases;
- one offline-evaluated Skill Candidate;
- zero approvals in the visual state;
- Fulfillment and Review Experience Paths completed;
- Seller Peer skipped because the single-seller fixture lacks the required diversity;
- fresh DeepSeek V4 runtime identity and retry zero.

Dates, Run IDs, token counts, and latency values in the raster are visual placeholders only. The implementation must read them from API data and Domain Events; it must not copy these literal placeholder values.

## Generation iterations

1. Initial three-column visual master: layout accepted, but rejected because it invented unsupported business Cases and displayed the wrong model identity.
2. Evidence-correct edit: content improved, but rejected because the generator collapsed the Codex-like three-column workspace and removed the bottom command surface.
3. Selected review candidate: preserves the initial workspace architecture and uses evidence-correct Case, Capability, Skill, and DeepSeek identity content.

## Final prompt

```text
Generate a new final visual-master UI mockup using the two previously generated images as references.
Input images: Image 1 is the layout and interaction reference; Image 2 is the evidence-correct content reference.

Use case: ui-mockup
Asset type: final high-fidelity desktop web application visual master and Commerce Overview screen
Primary request: Combine Image 1's exact three-column Codex-inspired workspace architecture with Image 2's evidence-correct metrics and cases. This is a new generation, not a loose redesign.

Layout invariants from Image 1:
- wide 16:10 desktop screenshot
- full-height 228px dark graphite left sidebar with the complete navigation
- compact top search/command bar
- warm off-white central canvas
- fixed 320px right-side "Agent runtime" inspector containing Goal Loop, Paths, and Runtime metadata
- bottom case-aware command/chat input spanning the center canvas
- compact operational tables and authoritative event stream
Do not collapse the right inspector into a main-card grid. Do not remove the bottom command input.

Left sidebar exact hierarchy: "Commerce Agent", "Demo Workspace", "Overview", "Data Inbox", "Capabilities", "Cases", "Actions", "Runs", "Skills & Evals", "War Room", "Settings". Highlight "Overview".

Main heading: "Commerce Overview". Subtitle: "Evidence-backed diagnosis, actions, and follow-up."
Top cards, exact evidence-correct content:
- "Uploaded tables" — "6"
- "Gold cases" — "3"
- "Offline candidates" — "1"
- "Awaiting approval" — "0"
No comparison-to-prior-period text.

Priority cases table must contain exactly:
1. "Late delivery spike — Seller 4869" | "+31.6pp late delivery" | "High" | "Investigating"
2. "Review score decline — Seller 0b90" | "-0.94 review score" | "High" | "Investigating"
3. "Missing review capability" | "order_reviews unavailable" | "Medium" | "Blocked"
Then a subtle empty row: "No additional priority cases". Do not add cancellation, return, payment, inventory, GMV, CTR, ROI, or profit rows.

Event stream exact event types: "case.opened", "path.completed", "evidence.barrier_released", "verification.completed", "skill_candidate.offline_evaluated". Last event description: "Regression and holdout passed".

Right inspector exact structure:
Title "Agent runtime".
Goal Loop vertical trace: "Goal", "Route", "Fan-out", "Evidence barrier", "Fresh verification", "Stop". Stop subtitle: "Candidate action ready".
Paths: "Fulfillment — completed", "Review Experience — completed", "Seller Peer — skipped: capability unavailable".
Runtime metadata must include exact model text "deepseek-v4-flash" and badge "retry 0". Include technical token and latency telemetry only, no business KPI.

Bottom input placeholder: "Ask about this workspace or attach commerce data..." with attachment and send controls.

Style: realistic implementable product UI; restrained Codex-inspired workspace, original assets; black/graphite sidebar; warm off-white canvas; charcoal typography; thin cool-gray borders; 8px radii; almost no shadows; teal for verified, amber for review/approval, red only for severity. Compact neutral sans-serif plus small monospace telemetry. High density, highly scannable.

Constraints: preserve Image 1 layout and navigation completeness; use Image 2 evidence-correct content; no logos/trademarks/copied wordmark; no stock art; no gradients beyond a barely perceptible surface tint; no fake loading; no invented business metrics; no watermark.
```

## Implementation invariants

- The raster is a design reference, never a page background.
- Visible business state must come from Commerce API contracts.
- Agent activity must come from ordered Domain Events.
- Runtime metadata must come from fresh model telemetry.
- Empty data must render explicit empty, unavailable, or blocked states.
- Status meaning must remain readable without color.
- The right inspector may collapse below the main content on narrow screens, but its data hierarchy must remain intact.
