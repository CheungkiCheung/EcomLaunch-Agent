import type { StoreCrewAgent, StoreCrewRole } from "./store-crew-activity";

export type StoreRoomPoint = { x: number; y: number };

export const STORE_HOME_POINTS: Record<StoreCrewRole, StoreRoomPoint> = {
  lead: { x: 50, y: 33 },
  explore: { x: 16, y: 56 },
  analyst: { x: 72, y: 62 },
  verifier: { x: 29, y: 74 },
};

const ROAM_POINTS: Record<Exclude<StoreCrewRole, "lead">, StoreRoomPoint[]> = {
  explore: [
    { x: 22, y: 66 },
    { x: 39, y: 58 },
    { x: 24, y: 50 },
  ],
  analyst: [
    { x: 67, y: 72 },
    { x: 55, y: 63 },
    { x: 79, y: 49 },
  ],
  verifier: [
    { x: 38, y: 79 },
    { x: 47, y: 66 },
    { x: 24, y: 68 },
  ],
};

function roleHash(role: StoreCrewRole) {
  return [...role].reduce((total, value) => total + value.charCodeAt(0), 0);
}

export function targetPointForAgent(
  agent: Pick<StoreCrewAgent, "id" | "active">,
  tick: number,
): StoreRoomPoint {
  if (agent.id === "lead" || agent.active) {
    return STORE_HOME_POINTS[agent.id];
  }
  const points = ROAM_POINTS[agent.id];
  return (
    points[(tick + roleHash(agent.id)) % points.length] ??
    STORE_HOME_POINTS[agent.id]
  );
}

export function walkingFrame(
  previous: StoreRoomPoint,
  target: StoreRoomPoint,
): "walk-left" | "walk-right" | "walk-up" | "walk-down" {
  const dx = target.x - previous.x;
  const dy = target.y - previous.y;
  if (Math.abs(dy) > Math.abs(dx)) {
    return dy < 0 ? "walk-up" : "walk-down";
  }
  return dx < 0 ? "walk-left" : "walk-right";
}
