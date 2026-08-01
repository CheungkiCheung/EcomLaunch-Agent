import { describe, expect, it } from "vitest";

import {
  STORE_HOME_POINTS,
  targetPointForAgent,
  walkingFrame,
} from "@/components/workspace/store-operator/store-war-room-motion";

describe("store war room motion", () => {
  it("returns an active agent to its workstation", () => {
    expect(targetPointForAgent({ id: "analyst", active: true }, 8)).toEqual(
      STORE_HOME_POINTS.analyst,
    );
  });

  it("moves an idle agent between deterministic roam points", () => {
    expect(
      targetPointForAgent({ id: "explore", active: false }, 0),
    ).not.toEqual(targetPointForAgent({ id: "explore", active: false }, 1));
  });

  it("chooses a directional walking frame", () => {
    expect(walkingFrame({ x: 10, y: 10 }, { x: 30, y: 11 })).toBe("walk-right");
    expect(walkingFrame({ x: 10, y: 20 }, { x: 11, y: 5 })).toBe("walk-up");
  });
});
