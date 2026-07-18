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
  shadow?: {
    width: number;
    height: number;
    offsetX?: number;
    offsetY?: number;
    alpha?: number;
  };
};

export type WarRoomArtifactItemAsset = {
  id: string;
  src: string;
  width: number;
  height: number;
};

export const WAR_ROOM_BACKGROUND = {
  src: "/images/ecom-launch/war-room/room/background.png",
  width: 1080,
  height: 756,
};

export const WAR_ROOM_AGENT_SPRITE_SIZE: Record<
  LaunchCrewAgent["id"],
  { width: number; height: number }
> = {
  "market-voc-researcher": { width: 64, height: 124 },
  "offer-architect": { width: 66, height: 119 },
  "launch-director": { width: 86, height: 136 },
  "evidence-checker": { width: 64, height: 119 },
  "growth-analyst": { width: 73, height: 124 },
  "asset-studio": { width: 75, height: 124 },
};

export const WAR_ROOM_PROPS: WarRoomPropAsset[] = [
  {
    id: "market-station",
    waypoint: "marketDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 132,
    height: 144,
    offsetX: -8,
    offsetY: 20,
    shadow: { width: 120, height: 30, offsetY: -3 },
  },
  {
    id: "offer-station",
    waypoint: "offerDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 132,
    height: 144,
    offsetX: -8,
    offsetY: 14,
    shadow: { width: 120, height: 30, offsetY: -3 },
  },
  {
    id: "evidence-station",
    waypoint: "evidenceDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 132,
    height: 144,
    offsetX: 10,
    offsetY: 20,
    shadow: { width: 120, height: 30, offsetY: -3 },
  },
  {
    id: "growth-station",
    waypoint: "growthDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 132,
    height: 144,
    offsetX: 0,
    offsetY: 16,
    shadow: { width: 120, height: 30, offsetY: -3 },
  },
  {
    id: "asset-station",
    waypoint: "assetDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 132,
    height: 144,
    offsetX: 10,
    offsetY: 14,
    shadow: { width: 120, height: 30, offsetY: -3 },
  },
  {
    id: "director-command-console",
    waypoint: "directorDesk",
    src: "/images/ecom-launch/war-room/props/command-console.png",
    width: 260,
    height: 132,
    offsetX: 0,
    offsetY: 34,
    shadow: { width: 208, height: 38, offsetY: -4, alpha: 0.16 },
  },
  {
    id: "big-screen",
    waypoint: "bigScreen",
    src: "/images/ecom-launch/war-room/props/big-screen.png",
    width: 186,
    height: 80,
    offsetX: 0,
    offsetY: -2,
  },
  {
    id: "whiteboard",
    waypoint: "whiteboard",
    src: "/images/ecom-launch/war-room/props/whiteboard.png",
    width: 156,
    height: 101,
    offsetX: -20,
    offsetY: -2,
  },
  {
    id: "artifact-conveyor",
    waypoint: "artifactConveyor",
    src: "/images/ecom-launch/war-room/props/artifact-conveyor.png",
    width: 168,
    height: 136,
    offsetX: 4,
    offsetY: 28,
    shadow: { width: 158, height: 34, offsetY: -5, alpha: 0.14 },
  },
  {
    id: "coffee",
    waypoint: "coffee",
    src: "/images/ecom-launch/war-room/props/coffee-station.png",
    width: 124,
    height: 136,
    offsetX: 4,
    offsetY: 26,
    shadow: { width: 108, height: 30, offsetY: -4, alpha: 0.14 },
  },
];

export const WAR_ROOM_ARTIFACT_ITEMS: WarRoomArtifactItemAsset[] = [
  "package",
  "product-card",
  "research-report",
  "evidence-checklist",
  "creative-thumbnail",
  "analytics-folder",
  "launch-calendar",
  "approval-stamp",
].map((id) => ({
  id,
  src: `/images/ecom-launch/war-room/artifacts/${id}.png`,
  width: 42,
  height: 42,
}));

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
      src: "/images/ecom-launch/war-room/agents/launch-director/idle.png",
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
    src: `/images/ecom-launch/war-room/agents/${agent.id}/${frame}.png`,
    ...WAR_ROOM_AGENT_SPRITE_SIZE[agent.id],
    frame,
    standalone: true,
  };
}
