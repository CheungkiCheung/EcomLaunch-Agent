import { describe, expect, it } from "vitest";

import type {
  LaunchCrewAgent,
  LaunchCrewRole,
} from "@/components/workspace/ecom-launch/launch-crew-activity-model";
import {
  AGENT_HOME_WAYPOINTS,
  buildWarRoomPath,
  buildWarRoomMotion,
  motionStateForAgent,
  WAR_ROOM_WAYPOINTS,
} from "@/components/workspace/ecom-launch/war-room-motion";

function agent(
  id: LaunchCrewRole,
  overrides: Partial<LaunchCrewAgent> = {},
): Pick<LaunchCrewAgent, "id" | "active" | "status"> {
  return {
    id,
    active: false,
    status: "idle",
    ...overrides,
  };
}

describe("war room motion model", () => {
  it("keeps the launch director seated at the command station", () => {
    const director = agent("launch-director", {
      active: true,
      status: "working",
    });

    expect(motionStateForAgent(director)).toBe("seated");

    const [motion] = buildWarRoomMotion([director], 4);
    expect(motion).toMatchObject({
      id: "launch-director",
      state: "seated",
      home: "directorDesk",
      position: WAR_ROOM_WAYPOINTS.directorDesk,
      target: null,
    });
  });

  it("lets idle non-director agents roam away from their home station", () => {
    const [motion] = buildWarRoomMotion([agent("market-voc-researcher")], 2);

    expect(motion?.state).toBe("roaming");
    expect(motion?.targetWaypoint).not.toBeNull();
    expect(
      ["leftWalkway", "whiteboard", "bigScreen", "coffee"].includes(
        motion?.targetWaypoint ?? "",
      ),
    ).toBe(true);
  });

  it("sends active agents back to their own station", () => {
    const [motion] = buildWarRoomMotion([
      agent("offer-architect", { active: true, status: "working" }),
    ]);

    expect(motion).toMatchObject({
      state: "returning_home",
      home: AGENT_HOME_WAYPOINTS["offer-architect"],
      position: WAR_ROOM_WAYPOINTS.offerDesk,
      targetWaypoint: "offerDesk",
      target: WAR_ROOM_WAYPOINTS.offerDesk,
    });
    expect(motion?.previousPosition).not.toEqual(WAR_ROOM_WAYPOINTS.offerDesk);
    expect(motion?.path.at(-1)).toEqual(WAR_ROOM_WAYPOINTS.offerDesk);
    expect(motion?.path).toContainEqual(WAR_ROOM_WAYPOINTS.centerWalkway);
  });

  it("routes completed agents to the artifact conveyor", () => {
    const [motion] = buildWarRoomMotion([
      agent("asset-studio", { status: "done" }),
    ]);

    expect(motion).toMatchObject({
      state: "reporting",
      targetWaypoint: "artifactConveyor",
      target: WAR_ROOM_WAYPOINTS.artifactConveyor,
    });
    expect(motion?.position).not.toEqual(WAR_ROOM_WAYPOINTS.artifactConveyor);
    expect(
      Math.hypot(
        (motion?.position.x ?? 0) - WAR_ROOM_WAYPOINTS.artifactConveyor.x,
        (motion?.position.y ?? 0) - WAR_ROOM_WAYPOINTS.artifactConveyor.y,
      ),
    ).toBeLessThanOrEqual(13);
    expect(motion?.path.at(-1)).toEqual(motion?.position);
  });

  it("spreads reporting agents around the conveyor so larger sprites do not stack", () => {
    const motions = buildWarRoomMotion([
      agent("market-voc-researcher", { status: "done" }),
      agent("asset-studio", { status: "done" }),
    ]);
    const positions = motions.map((motion) => motion.position);

    expect(positions[0]).not.toEqual(positions[1]);
    expect(
      Math.hypot(
        (positions[0]?.x ?? 0) - (positions[1]?.x ?? 0),
        (positions[0]?.y ?? 0) - (positions[1]?.y ?? 0),
      ),
    ).toBeGreaterThan(15);
    expect(
      motions.every((motion) => motion.targetWaypoint === "artifactConveyor"),
    ).toBe(true);
  });

  it("keeps blocked agents at home with a blocked state", () => {
    const [motion] = buildWarRoomMotion([
      agent("evidence-checker", { status: "error" }),
    ]);

    expect(motion).toMatchObject({
      state: "blocked",
      targetWaypoint: "evidenceDesk",
      target: WAR_ROOM_WAYPOINTS.evidenceDesk,
    });
  });

  it("routes long moves through walkways instead of a direct table-crossing line", () => {
    const path = buildWarRoomPath(
      WAR_ROOM_WAYPOINTS.marketDesk,
      WAR_ROOM_WAYPOINTS.assetDesk,
    );

    expect(path.length).toBeGreaterThan(2);
    expect(path).toContainEqual(WAR_ROOM_WAYPOINTS.leftWalkway);
    expect(path).toContainEqual(WAR_ROOM_WAYPOINTS.centerWalkway);
    expect(path).toContainEqual(WAR_ROOM_WAYPOINTS.rightWalkway);
    expect(path.at(-1)).toEqual(WAR_ROOM_WAYPOINTS.assetDesk);
  });
});
