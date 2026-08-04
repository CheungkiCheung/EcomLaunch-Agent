import { describe, expect, it } from "vitest";

import { WAR_ROOM_ACTORS } from "@/components/workspace/war-room/config";
import {
  ORIGINAL_ACTOR_LAYOUT,
  ORIGINAL_OFFICE_COLLISIONS,
  ORIGINAL_OFFICE_HEIGHT,
  ORIGINAL_OFFICE_POIS,
  ORIGINAL_OFFICE_WIDTH,
  originalCharacterPath,
  pointTouchesOfficeCollision,
} from "@/components/workspace/war-room/original-office-layout";

describe("original War Room visual layout", () => {
  it("provides an original directional sprite and runtime layout for every actor", () => {
    for (const actor of WAR_ROOM_ACTORS) {
      const layout = ORIGINAL_ACTOR_LAYOUT[actor.id];
      expect(layout).toBeDefined();
      expect(originalCharacterPath(actor.id)).toBe(
        `/war-room-original/characters/${actor.id}.png`,
      );
    }
  });

  it("keeps actor homes, work points, and idle POIs inside walkable space", () => {
    for (const layout of Object.values(ORIGINAL_ACTOR_LAYOUT)) {
      expect(layout.homeX).toBeGreaterThan(0);
      expect(layout.homeX).toBeLessThan(ORIGINAL_OFFICE_WIDTH);
      expect(layout.homeY).toBeGreaterThan(0);
      expect(layout.homeY).toBeLessThan(ORIGINAL_OFFICE_HEIGHT);
      expect(pointTouchesOfficeCollision(layout.homeX, layout.homeY, 6)).toBe(
        false,
      );
      expect(pointTouchesOfficeCollision(layout.workX, layout.workY, 6)).toBe(
        false,
      );
    }

    for (const poi of ORIGINAL_OFFICE_POIS) {
      expect(pointTouchesOfficeCollision(poi.x, poi.y, 6)).toBe(false);
    }
  });

  it("keeps every collision rectangle inside the generated map bounds", () => {
    for (const rect of ORIGINAL_OFFICE_COLLISIONS) {
      expect(rect.width).toBeGreaterThan(0);
      expect(rect.height).toBeGreaterThan(0);
      expect(rect.x).toBeGreaterThanOrEqual(0);
      expect(rect.y).toBeGreaterThanOrEqual(0);
      expect(rect.x + rect.width).toBeLessThanOrEqual(ORIGINAL_OFFICE_WIDTH);
      expect(rect.y + rect.height).toBeLessThanOrEqual(ORIGINAL_OFFICE_HEIGHT);
    }
  });
});
