# Commerce Master Shell Visual v1

## Status

- Generated with the built-in `imagegen` tool on 2026-07-20.
- Rejected after user review on 2026-07-20.
- Superseded by the Chinese, light, Codex-inspired `master-shell-visual-v2.png` direction.
- React implementation was not started from this version.
- Raster reference: `docs/design/commerce/mockups/master-shell-visual-v1.png`.
- Canvas: 1586 × 992 PNG.

## Page goal

Define the reusable application container for the Case-first Commerce Workspace:

- global navigation and active-Case switching on the left;
- one authoritative Case investigation surface in the center;
- Evidence, Hypothesis, Action and Data inspection on the right;
- inspectable Agent Runtime telemetry in a collapsed drawer;
- Case-bound Chat as a secondary command surface rather than the product itself.

This is a shell contract, not an Overview metrics page and not a complete Case Detail implementation. Later pages must preserve its navigation, panel proportions, typography, surfaces, composer and runtime hierarchy unless an explicit visual review changes the master.

## Product state represented

The visual uses the existing `GC-FULFILLMENT-001` scenario as a representative active Case:

- a high-severity late-delivery Case for Seller 4869;
- an Investigation Run with Fulfillment Evidence;
- an Evidence Barrier and fresh Verification completion;
- a candidate Action ready for review;
- a released lease and fresh DeepSeek V4 runtime metadata.

The raster is not a source of business truth. Dates, time zones, `CASE-1042`, Run IDs, source-system labels, individual Evidence descriptions, approval policy and runtime counters are visual placeholders. The React implementation must obtain them from Commerce API contracts, repositories and ordered Domain Events. In particular:

- do not copy the raster's `PST` / `PDT` combination;
- do not hard-code `Metrics Warehouse`, `OMS` or `CS Tickets`;
- do not assume `approval not required` before evaluating the Action Policy;
- do not mark a VOC item as contradicting unless its persisted Evidence relation says so;
- do not display `2 paths completed` unless the current Run projection supports it.

## State matrix

| Surface | Primary state in v1 | Required non-happy states for implementation |
| --- | --- | --- |
| Workspace | Demo Workspace selected | unavailable, access denied |
| Case navigation | one active high-severity Case plus one secondary Case | empty queue, stale projection |
| Case | investigating | blocked, waiting, resolved, reopened |
| Timeline | ordered Domain Events with one expanded Path result | no events, unknown event, partial Path, failed Run |
| Evidence inspector | required coverage complete with one contradiction | unavailable capability, missing lineage, unverified Evidence |
| Hypothesis | supported with caveat | unsupported, contradicted, superseded |
| Action | candidate ready for review | approval required, execution failed, rolled back, no action |
| Runtime drawer | completed paths, retry zero, lease released | queued, waiting, blocked, cancelled, unknown outcome |
| Composer | Case-bound and idle | attachment validation error, read-only mode, submit failure |

## Selected visual decisions

- Preserve the dark graphite full-height navigation from the Overview visual master.
- Use the center as a structured Domain Event timeline, not a transcript of Agent role messages.
- Keep the right inspector persistent and object-oriented: Evidence, Hypothesis, Action and Data.
- Keep the composer visible but visually subordinate to the Case state.
- Keep Agent Runtime collapsed by default; expose model, retry, Path and lease state without pretending the Agent is busy.
- Use compact rows, thin borders, eight-pixel radii and almost no shadows.
- Encode status in text and icons as well as color.
- Use red only for severity, teal for verified state and amber for caveat or approval state.

## Known visual gaps before implementation

- The generated right inspector uses more card boundaries than the final React version should need; implementation should prefer separators where hierarchy remains clear.
- The desktop visual does not define narrow-screen behavior. On smaller screens the right inspector becomes a drawer and the left navigation collapses, while preserving the same data hierarchy.
- Resizable-panel handles are visually subtle in the raster; the implementation needs keyboard-accessible resizing and persistent panel widths.
- The raster does not show focus, hover, error, loading, empty or reduced-motion states; these belong to component and browser QA.
- Some generated text is semantically illustrative rather than fixture-exact. API-backed rendering is authoritative.

## Generation prompt

```text
Use case: ui-mockup
Asset type: high-fidelity desktop web application master shell
Primary request: Create a shippable 1440×900-style desktop product UI for an original “Commerce Case Agent” workspace. This is the reusable application shell, not a marketing page and not an Overview statistics dashboard. It should feel restrained, dense, calm, and implementation-ready, inspired by the information hierarchy of modern coding-agent desktop tools without copying Codex branding, logos, or exact assets.

Scene/backdrop: full-frame desktop application screenshot with a warm off-white central surface, dark graphite navigation rail, thin cool-gray separators, almost no shadows.

Composition and layout:
- Wide 16:10 desktop frame.
- Fixed 228px dark graphite left sidebar spanning full height.
- Compact top command/search bar across the center workspace.
- Main Case workspace in the center, roughly 820px wide.
- Fixed 320px right inspector.
- A compact collapsed Runtime Drawer strip anchored above the bottom edge of the center and right workspace.
- A Case-bound command/chat composer at the bottom of the center workspace.
- Clear resizable-panel affordances, but no floating decorative windows.

Left sidebar hierarchy, render these labels verbatim and no extra navigation labels:
“Commerce Agent”
“Demo Workspace”
“Overview”
“Data Inbox”
“Capabilities”
“Cases”
“Actions”
“Runs”
“Skills & Evals”
“War Room”
“Settings”
Highlight “Cases”. Below the main navigation, include a compact “Active cases” section with two rows: “Late delivery spike” and “Review score decline”, using small status dots and truncated seller IDs. Keep it functional and quiet.

Top bar:
- Search placeholder: “Search or run a command…”
- Small workspace breadcrumb: “Cases / CASE-1042”
- Keyboard shortcut hint, notification control, and user avatar represented by simple original icons.

Center Case workspace:
- Header title: “Late delivery spike — Seller 4869”
- Small badges: “High”, “Investigating”, “Fulfillment”
- Subtitle: “+31.6pp late delivery in the current window”
- A compact metadata line for analysis window and data freshness.
- Under the header, a segmented view switch with exactly: “Timeline”, “Evidence”, “Run graph”. Highlight “Timeline”.
- Main content is a chronological investigation timeline built from structured Domain Events, not chat bubbles. Use five compact event rows with readable event names: “case.opened”, “run.started”, “path.completed”, “evidence.barrier_released”, “verification.completed”.
- Each row should show timestamp, event icon, concise human description, and a source/run link. One expanded row for “path.completed” should reveal two compact evidence findings and a “View evidence” control.
- Include a small explicit state block reading “Candidate action ready” near the bottom of the timeline, followed by one restrained primary button “Review action”.
- Do not show metric summary cards, charts, GMV, CTR, ROI, profit, inventory, ad spend, fabricated causality, or marketing copy.

Right inspector:
- Header “Case inspector”.
- Compact tabs exactly: “Evidence”, “Hypothesis”, “Action”, “Data”. Highlight “Evidence”.
- Evidence coverage block: “Required 4 / 4”, “Contradicting 1”.
- Three dense evidence rows with type badges: “Metric”, “Fact”, “VOC”. Use short descriptions about late delivery, lead-time increase, and one customer report. Each row includes source lineage and a verified/contradicting status visible in text, not color alone.
- Below, a “Working hypothesis” section with one concise hypothesis and status “supported with caveat”.
- A small “Next action” preview: “Review carrier SLA action” with status “approval not required”.
- Do not imply any action has executed.

Bottom runtime drawer:
- Collapsed horizontal strip labeled “Agent runtime”.
- Show exact runtime chips: “deepseek-v4-flash”, “retry 0”, “2 paths completed”, “lease released”.
- Chevron to expand. No fake spinner, no animated agent avatars, no ‘thinking’ indicator.

Bottom composer:
- Placeholder text exactly: “Ask about this case or attach commerce data…”
- Attachment button, context badge “CASE-1042”, and send button.
- Composer is secondary to the structured Case workspace.

Style/medium: realistic product UI, original design, high information density, compact neutral sans-serif typography with small monospace telemetry. Dark graphite sidebar; warm off-white canvas; charcoal text; subtle cool-gray borders; 8px corner radii; teal only for verified; amber for caveat/approval; muted red only for high severity. Status meaning must remain legible without relying on color. Icons are simple thin-line originals.

Constraints: no Codex wordmark, no copied brand assets, no logos or trademarks, no landing-page hero, no neon, no gradients except a barely perceptible warm surface tint, no excessive cards, no glassmorphism, no fake loading or moving agents, no giant empty areas, no stock illustration, no decorative analytics charts, no unsupported business metrics, no watermark. Keep text readable and avoid tiny illegible filler. Render only the requested labels; do not invent long paragraphs. The result must look feasible to implement in Next.js/React with resizable panels and structured Domain Event data.
```

## Approval gate

User approval is required before creating Master Shell React components, View Models or browser tests. After approval, implementation must follow:

```text
RED: event-to-view-model, unknown-event, navigation and panel behavior tests
→ GREEN: minimum feature-flagged Master Shell
→ REFACTOR: shared Commerce layout primitives
→ VERIFY: unit, typecheck, lint, browser interaction, screenshot and responsive QA
```
