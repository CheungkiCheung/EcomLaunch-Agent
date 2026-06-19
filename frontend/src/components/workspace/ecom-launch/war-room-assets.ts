import type { LaunchCrewAgent } from "./launch-crew-activity-model";
import type { WarRoomMotionState, WarRoomWaypointId } from "./war-room-motion";

export type WarRoomCharacterFrame =
  | "idle"
  | "walk-left"
  | "walk-right"
  | "walk-up"
  | "walk-down"
  | "work";

export type WarRoomPropAsset = {
  id: string;
  waypoint: WarRoomWaypointId;
  src: string;
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
};

export const WAR_ROOM_AGENT_SPRITE_SIZE: Record<
  LaunchCrewAgent["id"],
  { width: number; height: number }
> = {
  "market-voc-researcher": { width: 80, height: 98 },
  "offer-architect": { width: 80, height: 98 },
  "launch-director": { width: 86, height: 102 },
  "evidence-checker": { width: 80, height: 98 },
  "growth-analyst": { width: 80, height: 98 },
  "asset-studio": { width: 80, height: 98 },
};

export const WAR_ROOM_PROPS: WarRoomPropAsset[] = [
  {
    id: "market-station",
    waypoint: "marketDesk",
    src: "/images/ecom-launch/war-room/props/market-voc-researcher-station.svg",
    width: 96,
    height: 72,
    offsetX: -18,
    offsetY: -8,
  },
  {
    id: "offer-station",
    waypoint: "offerDesk",
    src: "/images/ecom-launch/war-room/props/offer-architect-station.svg",
    width: 96,
    height: 72,
    offsetX: -18,
    offsetY: -8,
  },
  {
    id: "evidence-station",
    waypoint: "evidenceDesk",
    src: "/images/ecom-launch/war-room/props/evidence-checker-station.svg",
    width: 96,
    height: 72,
    offsetX: 18,
    offsetY: -8,
  },
  {
    id: "growth-station",
    waypoint: "growthDesk",
    src: "/images/ecom-launch/war-room/props/growth-analyst-station.svg",
    width: 96,
    height: 72,
    offsetX: 0,
    offsetY: 0,
  },
  {
    id: "asset-station",
    waypoint: "assetDesk",
    src: "/images/ecom-launch/war-room/props/asset-studio-station.svg",
    width: 96,
    height: 72,
    offsetX: 18,
    offsetY: -8,
  },
  {
    id: "director-command-console",
    waypoint: "directorDesk",
    src: "/images/ecom-launch/war-room/props/command-console.svg",
    width: 180,
    height: 116,
    offsetX: 0,
    offsetY: 28,
  },
  {
    id: "big-screen",
    waypoint: "bigScreen",
    src: "/images/ecom-launch/war-room/props/big-screen.svg",
    width: 140,
    height: 58,
    offsetX: 0,
    offsetY: -10,
  },
  {
    id: "whiteboard",
    waypoint: "whiteboard",
    src: "/images/ecom-launch/war-room/props/whiteboard.svg",
    width: 112,
    height: 56,
    offsetX: -6,
    offsetY: -4,
  },
  {
    id: "artifact-conveyor",
    waypoint: "artifactConveyor",
    src: "/images/ecom-launch/war-room/props/artifact-conveyor.svg",
    width: 108,
    height: 42,
    offsetX: 0,
    offsetY: 10,
  },
  {
    id: "coffee",
    waypoint: "coffee",
    src: "/images/ecom-launch/war-room/props/coffee.svg",
    width: 48,
    height: 50,
    offsetX: 0,
    offsetY: 6,
  },
];

function characterFrameForMotion(
  motionState: WarRoomMotionState,
  deltaX: number,
  deltaY: number,
): WarRoomCharacterFrame {
  if (motionState === "returning_home" || motionState === "working") {
    return "work";
  }
  if (motionState === "blocked") {
    return "idle";
  }
  if (motionState !== "roaming" && motionState !== "reporting") {
    return "idle";
  }
  if (Math.abs(deltaY) > Math.abs(deltaX) && deltaY < -1) {
    return "walk-up";
  }
  if (Math.abs(deltaY) > Math.abs(deltaX) && deltaY > 1) {
    return "walk-down";
  }
  if (deltaX < -1) {
    return "walk-left";
  }
  if (deltaX > 1) {
    return "walk-right";
  }
  return "idle";
}

export function warRoomCharacterSprite(
  agent: Pick<LaunchCrewAgent, "id">,
  motion: {
    state: WarRoomMotionState;
    previousPosition: { x: number; y: number };
    position: { x: number; y: number };
  },
) {
  if (agent.id === "launch-director") {
    return {
      src: "/images/ecom-launch/war-room/agents/launch-director/idle.svg",
      ...WAR_ROOM_AGENT_SPRITE_SIZE["launch-director"],
      frame: "idle" satisfies WarRoomCharacterFrame,
      standalone: true,
    };
  }

  const frame = characterFrameForMotion(
    motion.state,
    motion.position.x - motion.previousPosition.x,
    motion.position.y - motion.previousPosition.y,
  );

  return {
    src: `/images/ecom-launch/war-room/agents/${agent.id}/${frame}.svg`,
    ...WAR_ROOM_AGENT_SPRITE_SIZE[agent.id],
    frame,
    standalone: true,
  };
}
