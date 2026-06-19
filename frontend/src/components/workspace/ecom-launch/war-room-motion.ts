import type {
  LaunchCrewAgent,
  LaunchCrewRole,
} from "./launch-crew-activity-model";

export type WarRoomPoint = {
  x: number;
  y: number;
};

export type WarRoomWaypointId =
  | "marketDesk"
  | "offerDesk"
  | "directorDesk"
  | "evidenceDesk"
  | "assetDesk"
  | "growthDesk"
  | "whiteboard"
  | "coffee"
  | "artifactConveyor"
  | "bigScreen"
  | "leftWalkway"
  | "rightWalkway"
  | "centerWalkway"
  | "lowerWalkway";

export type WarRoomMotionState =
  | "seated"
  | "roaming"
  | "returning_home"
  | "working"
  | "reporting"
  | "blocked";

export type WarRoomAgentMotion = {
  id: LaunchCrewRole;
  home: WarRoomWaypointId;
  previousPosition: WarRoomPoint;
  position: WarRoomPoint;
  path: WarRoomPoint[];
  target: WarRoomPoint | null;
  targetWaypoint: WarRoomWaypointId | null;
  state: WarRoomMotionState;
};

export const WAR_ROOM_WAYPOINTS: Record<WarRoomWaypointId, WarRoomPoint> = {
  marketDesk: { x: 18, y: 28 },
  offerDesk: { x: 20, y: 68 },
  directorDesk: { x: 50, y: 44 },
  evidenceDesk: { x: 82, y: 28 },
  assetDesk: { x: 82, y: 68 },
  growthDesk: { x: 50, y: 78 },
  whiteboard: { x: 38, y: 18 },
  coffee: { x: 12, y: 78 },
  artifactConveyor: { x: 66, y: 66 },
  bigScreen: { x: 50, y: 16 },
  leftWalkway: { x: 30, y: 46 },
  rightWalkway: { x: 70, y: 46 },
  centerWalkway: { x: 50, y: 58 },
  lowerWalkway: { x: 36, y: 76 },
};

export const AGENT_HOME_WAYPOINTS: Record<LaunchCrewRole, WarRoomWaypointId> = {
  "market-voc-researcher": "marketDesk",
  "offer-architect": "offerDesk",
  "launch-director": "directorDesk",
  "evidence-checker": "evidenceDesk",
  "growth-analyst": "growthDesk",
  "asset-studio": "assetDesk",
};

const ROAM_WAYPOINTS: Record<LaunchCrewRole, WarRoomWaypointId[]> = {
  "market-voc-researcher": ["leftWalkway", "whiteboard", "bigScreen", "coffee"],
  "offer-architect": ["lowerWalkway", "whiteboard", "artifactConveyor"],
  "launch-director": ["directorDesk"],
  "evidence-checker": ["rightWalkway", "bigScreen", "artifactConveyor"],
  "growth-analyst": ["centerWalkway", "bigScreen", "artifactConveyor"],
  "asset-studio": ["rightWalkway", "artifactConveyor", "whiteboard"],
};

function deterministicIndex(id: string, tick: number, length: number) {
  let hash = tick;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) % 9973;
  }
  return hash % length;
}

function samePoint(a: WarRoomPoint, b: WarRoomPoint) {
  return a.x === b.x && a.y === b.y;
}

function nearestWalkway(point: WarRoomPoint): WarRoomPoint {
  if (point.y >= 66 && point.x < 58) {
    return WAR_ROOM_WAYPOINTS.lowerWalkway;
  }
  if (point.x < 42) {
    return WAR_ROOM_WAYPOINTS.leftWalkway;
  }
  if (point.x > 58) {
    return WAR_ROOM_WAYPOINTS.rightWalkway;
  }
  return WAR_ROOM_WAYPOINTS.centerWalkway;
}

export function buildWarRoomPath(
  from: WarRoomPoint,
  to: WarRoomPoint,
): WarRoomPoint[] {
  if (samePoint(from, to)) {
    return [to];
  }

  const path = [
    nearestWalkway(from),
    WAR_ROOM_WAYPOINTS.centerWalkway,
    nearestWalkway(to),
    to,
  ];

  return path.filter(
    (point, index) =>
      index === 0 || !samePoint(point, path[index - 1] ?? point),
  );
}

export function motionStateForAgent(
  agent: Pick<LaunchCrewAgent, "id" | "active" | "status">,
): WarRoomMotionState {
  if (agent.id === "launch-director") {
    return "seated";
  }
  if (agent.status === "error") {
    return "blocked";
  }
  if (agent.status === "done" || agent.status === "delivered") {
    return "reporting";
  }
  if (agent.active) {
    return "returning_home";
  }
  return "roaming";
}

export function buildWarRoomMotion(
  agents: Array<Pick<LaunchCrewAgent, "id" | "active" | "status">>,
  tick = 0,
): WarRoomAgentMotion[] {
  return agents.map((agent) => {
    const home = AGENT_HOME_WAYPOINTS[agent.id];
    const state = motionStateForAgent(agent);
    const roamTargets = ROAM_WAYPOINTS[agent.id];
    const roamWaypoint =
      roamTargets[deterministicIndex(agent.id, tick, roamTargets.length)] ??
      home;
    const previousRoamWaypoint =
      roamTargets[
        deterministicIndex(agent.id, Math.max(tick - 1, 0), roamTargets.length)
      ] ?? home;
    const targetWaypoint =
      state === "roaming"
        ? roamWaypoint
        : state === "reporting"
          ? "artifactConveyor"
          : home;
    const position =
      state === "roaming"
        ? WAR_ROOM_WAYPOINTS[roamWaypoint]
        : state === "reporting"
          ? WAR_ROOM_WAYPOINTS.artifactConveyor
          : WAR_ROOM_WAYPOINTS[home];
    const previousPosition =
      state === "roaming"
        ? WAR_ROOM_WAYPOINTS[previousRoamWaypoint]
        : state === "reporting"
          ? WAR_ROOM_WAYPOINTS[home]
          : state === "returning_home"
            ? WAR_ROOM_WAYPOINTS[previousRoamWaypoint]
            : position;

    return {
      id: agent.id,
      home,
      previousPosition,
      position,
      path: buildWarRoomPath(previousPosition, position),
      target:
        state === "seated" || state === "working"
          ? null
          : WAR_ROOM_WAYPOINTS[targetWaypoint],
      targetWaypoint,
      state,
    };
  });
}
