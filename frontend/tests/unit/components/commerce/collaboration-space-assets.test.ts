import { describe, expect, test } from "vitest";

import {
  commerceActorPlacement,
  commerceActorSprite,
  commerceStationSprite,
} from "@/components/commerce/collaboration-space-assets";

describe("commerce collaboration generated assets", () => {
  test("maps generic runtime profiles to original generated character sprites", () => {
    expect(commerceActorSprite("explore")).toBe(
      "/commerce/collaboration/actors/explore-v1.png",
    );
    expect(commerceActorSprite("analyst")).toBe(
      "/commerce/collaboration/actors/analyst-v1.png",
    );
    expect(commerceActorSprite("verifier")).toBe(
      "/commerce/collaboration/actors/verifier-v1.png",
    );
    expect(commerceActorSprite("operator")).toBe(
      "/commerce/collaboration/actors/operator-v1.png",
    );
  });

  test("uses a neutral operator visual for an unknown dynamic profile", () => {
    expect(commerceActorSprite("future-profile")).toBe(
      "/commerce/collaboration/actors/operator-v1.png",
    );
  });

  test("maps runtime stations to the generated task workstation set", () => {
    expect(commerceStationSprite("intake")).toBe(
      "/commerce/collaboration/stations/intake-v1.png",
    );
    expect(commerceStationSprite("analysis")).toBe(
      "/commerce/collaboration/stations/analysis-v1.png",
    );
    expect(commerceStationSprite("verification")).toBe(
      "/commerce/collaboration/stations/verification-v1.png",
    );
    expect(commerceStationSprite("action")).toBe(
      "/commerce/collaboration/stations/recovery-v1.png",
    );
    expect(commerceStationSprite("recovery")).toBe(
      "/commerce/collaboration/stations/recovery-v1.png",
    );
  });

  test("places four tasks in non-overlapping deterministic scene slots", () => {
    const placements = Array.from({ length: 4 }, (_, index) =>
      commerceActorPlacement(index, 4, `task-${index}`),
    );

    expect(placements).toEqual([
      { left: 28, top: 26 },
      { left: 72, top: 26 },
      { left: 28, top: 64 },
      { left: 72, top: 64 },
    ]);
    expect(
      new Set(placements.map(({ left, top }) => `${left}:${top}`)).size,
    ).toBe(4);
  });

  test("expands to a three-column grid for five or six real tasks", () => {
    const placements = Array.from({ length: 6 }, (_, index) =>
      commerceActorPlacement(index, 6, `task-${index}`),
    );

    expect(placements).toEqual([
      { left: 18, top: 26 },
      { left: 50, top: 26 },
      { left: 82, top: 26 },
      { left: 18, top: 64 },
      { left: 50, top: 64 },
      { left: 82, top: 64 },
    ]);
  });
});
