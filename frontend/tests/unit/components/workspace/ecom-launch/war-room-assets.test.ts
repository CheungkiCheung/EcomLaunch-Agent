import { describe, expect, it } from "vitest";

import {
  WAR_ROOM_BACKGROUND,
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
    expect(WAR_ROOM_BACKGROUND.src).toBe(
      "/images/ecom-launch/war-room/room/background.png",
    );
    expect(
      WAR_ROOM_PROPS.filter((prop) => prop.id !== "coffee").every((prop) =>
        prop.src.endsWith(".png"),
      ),
    ).toBe(true);
  });

  it("uses standalone war-room character assets for moving agents", () => {
    const sprite = warRoomCharacterSprite(
      { id: "market-voc-researcher" },
      {
        state: "roaming",
        previousPosition: { x: 50, y: 40 },
        position: { x: 18, y: 40 },
      },
    );

    expect(sprite).toMatchObject({
      standalone: true,
      frame: "walk-left",
    });
    expect(sprite.src).toBe(
      "/images/ecom-launch/war-room/agents/market-voc-researcher/walk-left.png",
    );
    expect(sprite.src).not.toContain("/sprites/agents/");
  });

  it("uses vertical walking frames when the y axis is the dominant motion", () => {
    const sprite = warRoomCharacterSprite(
      { id: "growth-analyst" },
      {
        state: "roaming",
        previousPosition: { x: 50, y: 76 },
        position: { x: 50, y: 16 },
      },
    );

    expect(sprite.frame).toBe("walk-up");
    expect(sprite.src).toBe(
      "/images/ecom-launch/war-room/agents/growth-analyst/walk-up.png",
    );
  });

  it("uses a work frame while assigned agents return to their station", () => {
    const sprite = warRoomCharacterSprite(
      { id: "asset-studio" },
      {
        state: "returning_home",
        previousPosition: { x: 66, y: 66 },
        position: { x: 82, y: 68 },
      },
    );

    expect(sprite.frame).toBe("work");
    expect(sprite.src).toBe(
      "/images/ecom-launch/war-room/agents/asset-studio/work.png",
    );
  });

  it("keeps the director as a separate seated character on the command console", () => {
    const sprite = warRoomCharacterSprite(
      { id: "launch-director" },
      {
        state: "seated",
        previousPosition: { x: 50, y: 44 },
        position: { x: 50, y: 44 },
      },
    );

    expect(sprite).toMatchObject({
      standalone: true,
      frame: "idle",
    });
    expect(sprite.src).toBe(
      "/images/ecom-launch/war-room/agents/launch-director/idle.png",
    );
  });
});
