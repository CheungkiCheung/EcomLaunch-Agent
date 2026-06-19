import { describe, expect, it } from "vitest";

import type {
  LaunchCrewAgent,
  LaunchCrewRole,
} from "@/components/workspace/ecom-launch/launch-crew-activity-model";
import {
  AGENT_HOME_WAYPOINTS,
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
  });

  it("routes completed agents to the artifact conveyor", () => {
    const [motion] = buildWarRoomMotion([
      agent("asset-studio", { status: "done" }),
    ]);

    expect(motion).toMatchObject({
      state: "reporting",
      position: WAR_ROOM_WAYPOINTS.artifactConveyor,
      targetWaypoint: "artifactConveyor",
      target: WAR_ROOM_WAYPOINTS.artifactConveyor,
    });
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
});
