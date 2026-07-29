# War Room

## Product boundary

The War Room is a standalone workspace visualization at `/workspace/war-room`.
It is not a third top-level agent and does not create a separate chat, task, or
runtime protocol.

The current cast mirrors the configured runtime:

- EcomLaunch / Launch Director
- Market & VOC Researcher
- Offer Architect
- Asset Studio
- Evidence Checker
- Growth Analyst (compatibility ID: `data-inspector`)

The four EcomLaunch specialists appear only when their real task/run state is
available. Growth Analyst remains an independent top-level agent and is not an
EcomLaunch subagent.

Tools such as web search, file inspection, SQL, writing, and file delivery are
shown as actor activities rather than additional characters.

## Runtime data flow

```text
DeerFlow threads and runs
  -> War Room adapter
  -> six actor snapshots
  -> React HUD + Phaser scene
```

The page polls the existing thread and run APIs. It does not introduce the
Agent Town WebSocket protocol, a player controller, a seat editor, or a second
local task store.

## Visual implementation

- React renders navigation, metrics, actor details, and chat links.
- Phaser 3 renders the generated office, actor movement, status bubbles, idle
  breathing, working pulses, completion feedback, and failure feedback.
- The Phaser scene is client-loaded only when the War Room route is opened.
- Actor positions are declarative in `config.ts`; runtime mapping stays in the
  pure `adapter.ts` module.

## Asset provenance

The white-and-cream office and character sheet were generated with the built-in
ImageGen tool for this project. No Agent Town, LimeZu, or other third-party
commercial visual assets are copied.

The original generated character sheet contains seven figures because it was
created for an earlier seven-role draft. The current UI maps and renders six
real roles; the unused figure remains only in the source asset and is not a
runtime actor.
