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
  marketDesk: { x: 18, y: 35 },
  offerDesk: { x: 26, y: 69 },
  directorDesk: { x: 50, y: 45 },
  evidenceDesk: { x: 84, y: 35 },
  assetDesk: { x: 84, y: 69 },
  growthDesk: { x: 50, y: 76 },
  whiteboard: { x: 41, y: 24 },
  coffee: { x: 12, y: 76 },
  artifactConveyor: { x: 66, y: 64 },
  bigScreen: { x: 55, y: 24 },
  leftWalkway: { x: 34, y: 52 },
  rightWalkway: { x: 68, y: 52 },
  centerWalkway: { x: 50, y: 60 },
  lowerWalkway: { x: 38, y: 74 },
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

const REPORTING_OFFSETS: Record<LaunchCrewRole, WarRoomPoint> = {
  "market-voc-researcher": { x: -10, y: -7 },
  "offer-architect": { x: -10, y: 8 },
  "launch-director": { x: 0, y: 0 },
  "evidence-checker": { x: 10, y: -7 },
  "growth-analyst": { x: -1, y: 11 },
  "asset-studio": { x: 10, y: 8 },
};

function pointWithOffset(point: WarRoomPoint, offset: WarRoomPoint) {
  return {
    x: point.x + offset.x,
    y: point.y + offset.y,
  };
}

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
    const reportingPosition = pointWithOffset(
      WAR_ROOM_WAYPOINTS.artifactConveyor,
      REPORTING_OFFSETS[agent.id],
    );
    const position =
      state === "roaming"
        ? WAR_ROOM_WAYPOINTS[roamWaypoint]
        : state === "reporting"
          ? reportingPosition
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
