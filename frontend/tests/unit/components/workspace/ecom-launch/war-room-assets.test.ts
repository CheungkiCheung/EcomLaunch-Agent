import { describe, expect, it } from "vitest";

import {
  WAR_ROOM_PROPS,
  warRoomCharacterSprite,
} from "@/components/workspace/ecom-launch/war-room-assets";

describe("war room asset model", () => {
  it("keeps workstation props separate from movable character sprites", () => {
    expect(WAR_ROOM_PROPS.map((prop) => prop.id)).toEqual(
      expect.arrayContaining([
        "market-station",
        "offer-station",
        "evidence-station",
        "growth-station",
        "asset-station",
        "director-command-console",
      ]),
    );

    for (const prop of WAR_ROOM_PROPS) {
      expect(prop.src).toContain("/war-room/props/");
    }
  });

  it("uses standalone war-room character assets for moving agents", () => {
    const sprite = warRoomCharacterSprite(
      { id: "market-voc-researcher" },
      {
        state: "roaming",
        previousPosition: { x: 50 },
        position: { x: 18 },
      },
    );

    expect(sprite).toMatchObject({
      standalone: true,
      frame: "walk-left",
    });
    expect(sprite.src).toBe(
      "/images/ecom-launch/war-room/agents/market-voc-researcher/walk-left.svg",
    );
    expect(sprite.src).not.toContain("/sprites/agents/");
  });

  it("keeps the director as a separate seated character on the command console", () => {
    const sprite = warRoomCharacterSprite(
      { id: "launch-director" },
      {
        state: "seated",
        previousPosition: { x: 50 },
        position: { x: 50 },
      },
    );

    expect(sprite).toMatchObject({
      standalone: true,
      frame: "idle",
    });
    expect(sprite.src).toBe(
      "/images/ecom-launch/war-room/agents/launch-director/idle.svg",
    );
  });
});
