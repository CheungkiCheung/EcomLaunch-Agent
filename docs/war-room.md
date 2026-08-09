# War Room

## Product boundary

The War Room is a standalone workspace visualization at `/workspace/war-room`.
It is not a third top-level agent and does not create a separate chat, task, or
runtime protocol.

The current cast mirrors the configured runtime:

- OpenSKU Launch Team / Launch Director
- Market & VOC Researcher
- Offer Architect
- Asset Studio
- Evidence Checker
- Growth Analyst (compatibility ID: `data-inspector`)

The four OpenSKU Launch Team specialists appear only when their real task/run state is
available. Growth Analyst remains an independent top-level agent and is not an
OpenSKU Launch Team subagent.

Tools such as web search, file inspection, SQL, writing, and file delivery are
shown as actor activities rather than additional characters.

## Runtime data flow

```text
OpenSKU threads and runs
  -> War Room adapter
  -> team-focused snapshots and persisted-event replay timelines
  -> React HUD + Phaser scene
```

The page polls the existing thread and run APIs. It does not introduce the
Agent Town WebSocket protocol, a player controller, a seat editor, or a second
local task store.

When a persisted request flow exists, the replay dock can switch between the
latest Launch Team and Growth Analyst runs. Launch replay reconstructs real
request, specialist handoff, tool result, preflight, delivery, and terminal
events. Growth replay reconstructs real data inspection, join/query,
deterministic experiment analysis, observation, decision, and terminal events.
If a team has no qualifying thread messages, the War Room does not fabricate a
replay source for it.

## Visual implementation

- React renders navigation and metrics over the scene, while the compact actor
  roster, selected-actor summary, chat/task/output actions, and run details live
  in a separate right sidebar so they never cover the playable floor.
- Run details follow the selected replay source: Launch shows web research and
  specialist task metrics, while Growth shows data-query and experiment metrics.
- Phaser 3 renders the original low-resolution office map, four-direction
  actors, movement, collision, A* pathfinding, status bubbles, completion
  feedback, and failure feedback.
- The Phaser scene is client-loaded only when the War Room route is opened.
- The initial camera uses a `0.72` zoom and preserves that zoom when player
  following begins, avoiding the previous first-movement jump from `0.62` to
  `1.0`.
- Runtime actor mapping stays in the pure `adapter.ts` module. Visual collision
  rectangles, home/work positions, and idle POIs are declarative in
  `original-office-layout.ts`.

## Asset provenance

The active warm cream/taupe office map and six four-direction character sheets
were generated with the built-in ImageGen tool and then processed with a
deterministic local asset build. The room layout and furniture remain
project-specific. The user-controlled `ecom-launch` actor uses the requested
rounded 噜噜 likeness; the five worker actors use original MC-inspired block
avatars rather than official Minecraft skins or the previous premade sheets.

The runtime no longer contains or loads the previous Agent Town/LimeZu map,
tilesets, premade character sheets, emotes, or pixel font. See
`docs/war-room-original-visual-system.md` for the visual and asset contracts.
