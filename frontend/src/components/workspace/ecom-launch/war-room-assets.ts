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

export const WAR_ROOM_BACKGROUND = {
  src: "/images/ecom-launch/war-room/room/background.png",
  width: 1000,
  height: 700,
};

export const WAR_ROOM_AGENT_SPRITE_SIZE: Record<
  LaunchCrewAgent["id"],
  { width: number; height: number }
> = {
  "market-voc-researcher": { width: 58, height: 112 },
  "offer-architect": { width: 60, height: 108 },
  "launch-director": { width: 78, height: 124 },
  "evidence-checker": { width: 58, height: 108 },
  "growth-analyst": { width: 66, height: 112 },
  "asset-studio": { width: 68, height: 112 },
};

export const WAR_ROOM_PROPS: WarRoomPropAsset[] = [
  {
    id: "market-station",
    waypoint: "marketDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 110,
    height: 120,
    offsetX: -2,
    offsetY: 28,
  },
  {
    id: "offer-station",
    waypoint: "offerDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 110,
    height: 120,
    offsetX: -4,
    offsetY: 20,
  },
  {
    id: "evidence-station",
    waypoint: "evidenceDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 110,
    height: 120,
    offsetX: 2,
    offsetY: 28,
  },
  {
    id: "growth-station",
    waypoint: "growthDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 110,
    height: 120,
    offsetX: 0,
    offsetY: 18,
  },
  {
    id: "asset-station",
    waypoint: "assetDesk",
    src: "/images/ecom-launch/war-room/props/workstation.png",
    width: 110,
    height: 120,
    offsetX: 4,
    offsetY: 20,
  },
  {
    id: "director-command-console",
    waypoint: "directorDesk",
    src: "/images/ecom-launch/war-room/props/command-console.png",
    width: 230,
    height: 116,
    offsetX: 0,
    offsetY: 32,
  },
  {
    id: "big-screen",
    waypoint: "bigScreen",
    src: "/images/ecom-launch/war-room/props/big-screen.png",
    width: 168,
    height: 73,
    offsetX: 0,
    offsetY: -2,
  },
  {
    id: "whiteboard",
    waypoint: "whiteboard",
    src: "/images/ecom-launch/war-room/props/whiteboard.png",
    width: 142,
    height: 91,
    offsetX: -18,
    offsetY: -2,
  },
  {
    id: "artifact-conveyor",
    waypoint: "artifactConveyor",
    src: "/images/ecom-launch/war-room/props/artifact-conveyor.png",
    width: 124,
    height: 102,
    offsetX: 0,
    offsetY: 28,
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
