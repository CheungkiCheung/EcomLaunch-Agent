# Original War Room visual system

## Goal

The runtime War Room uses an original low-resolution, top-down pixel office
instead of redistributing the Agent Town/LimeZu map, characters, tilesets,
emotes, or font assets.

The user-provided reference screenshot is used only to define general game-art
properties: camera angle, pixel density, compact character scale, thin dark
outlines, modular rooms, and sparse flat shading. The room geometry, furniture
arrangement, generated pixels, and runtime layout are new for this project.

## Visual contract

- Elevated orthographic top-down camera, not diamond isometric.
- Low logical resolution with nearest-neighbor scaling and no antialiasing.
- Pale cream canvas, warm taupe floors, muted lavender-cream walls, and warm
  wood furniture.
- One-to-two-pixel charcoal/navy outlines.
- Beige furniture with restrained orange, blue, green, red, and teal accents.
- A rounded four-direction 噜噜 protagonist for the user-controlled
  `ecom-launch` actor.
- Five original MC-inspired block-avatar office workers with minimal facial
  detail and four directions.
- Every direction is normalized to the same visible width, height, and foot
  baseline so turning does not change apparent character size.
- Clear corridors, shallow shadows, and no baked-in labels or runtime actors.

## Runtime asset contract

- Background: `frontend/public/war-room-original/office-map.png`.
- Characters: one `192x72` RGBA sheet per actor under
  `frontend/public/war-room-original/characters/`.
- Character frame size: `48x72`.
- Frame order: down, left, right, up.
- Collision rectangles, spawns, work points, and idle POIs are declared in
  `frontend/src/components/workspace/war-room/original-office-layout.ts`.
- Status emotes are rendered by Phaser text/graphics and do not depend on a
  third-party sprite sheet.

## Selected ImageGen prompts

The selected environment prompt requested an entirely original four-room AI
office while matching only the reference image's low-resolution pixel density,
orthographic top-down camera, muted gray-lavender palette, thin blue-gray
outlines, modular construction, sparse flat shading, and furniture scale. It
explicitly prohibited copying the reference layout, silhouettes, labels,
characters, UI, or exact pixels.

The selected character prompt requested a rounded pixel interpretation of the
user-selected 噜噜 protagonist plus five original MC-inspired office avatars.
It fixed the directional order to down, left, right, and up. The five office
workers do not copy premade characters or official Minecraft skins/textures.
The 噜噜 depiction is a user-directed character likeness; reuse or public
distribution should follow the rights applicable to that character.

## Deterministic build

Run the following command after changing the approved source images:

```bash
/Users/zhangqixiang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/build_original_war_room_assets.py
```

The build hardens alpha edges, reduces palettes without dithering, normalizes
character scale, and packs the four direction frames into stable runtime sheets.
