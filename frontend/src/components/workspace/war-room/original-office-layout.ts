import type { WarRoomActorId } from "./types";

export const ORIGINAL_OFFICE_WIDTH = 1492;
export const ORIGINAL_OFFICE_HEIGHT = 1054;
export const ORIGINAL_OFFICE_BACKGROUND = "/war-room-original/office-map.png";

export type OfficeCollisionRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type OriginalActorLayout = {
  homeX: number;
  homeY: number;
  workX: number;
  workY: number;
  facing: "down" | "left" | "right" | "up";
};

/**
 * Rectangles approximate the visible wall/furniture footprint in the generated
 * map. They intentionally leave wide corridors so both Arcade Physics and the
 * 16px A* grid agree on reachable paths.
 */
export const ORIGINAL_OFFICE_COLLISIONS: OfficeCollisionRect[] = [
  // Outer room shells and non-walkable canvas.
  { x: 0, y: 0, width: 1492, height: 28 },
  { x: 0, y: 0, width: 72, height: 1054 },
  { x: 1450, y: 0, width: 42, height: 1054 },
  { x: 0, y: 970, width: 620, height: 84 },
  { x: 805, y: 970, width: 687, height: 84 },
  { x: 70, y: 28, width: 635, height: 118 },
  { x: 705, y: 0, width: 165, height: 200 },
  { x: 870, y: 0, width: 580, height: 72 },
  { x: 70, y: 540, width: 485, height: 38 },
  { x: 555, y: 540, width: 45, height: 155 },
  { x: 30, y: 540, width: 42, height: 430 },
  { x: 870, y: 450, width: 580, height: 48 },
  { x: 850, y: 450, width: 48, height: 250 },

  // Command and research room furniture.
  { x: 92, y: 110, width: 130, height: 245 },
  { x: 292, y: 100, width: 360, height: 82 },
  { x: 250, y: 245, width: 305, height: 175 },
  { x: 115, y: 425, width: 180, height: 120 },
  { x: 645, y: 205, width: 112, height: 220 },

  // Research library furniture.
  { x: 900, y: 105, width: 540, height: 112 },
  { x: 1060, y: 250, width: 275, height: 96 },
  { x: 1370, y: 190, width: 80, height: 205 },

  // Content studio furniture.
  { x: 52, y: 585, width: 85, height: 315 },
  { x: 145, y: 565, width: 260, height: 110 },
  { x: 255, y: 690, width: 165, height: 115 },
  { x: 145, y: 835, width: 145, height: 112 },
  { x: 370, y: 835, width: 145, height: 112 },
  { x: 420, y: 570, width: 125, height: 120 },
  { x: 520, y: 790, width: 68, height: 120 },

  // Growth analytics room furniture.
  { x: 920, y: 500, width: 420, height: 150 },
  { x: 930, y: 665, width: 405, height: 145 },
  { x: 1365, y: 540, width: 78, height: 320 },
  { x: 900, y: 875, width: 220, height: 85 },
  { x: 1210, y: 870, width: 235, height: 90 },

  // Shared corridor cabinet and planters.
  { x: 660, y: 500, width: 92, height: 102 },
  { x: 570, y: 900, width: 78, height: 82 },
  { x: 790, y: 900, width: 78, height: 82 },
];

export const ORIGINAL_ACTOR_LAYOUT: Record<
  WarRoomActorId,
  OriginalActorLayout
> = {
  "ecom-launch": {
    homeX: 720,
    homeY: 880,
    workX: 715,
    workY: 440,
    facing: "up",
  },
  "market-voc-researcher": {
    homeX: 610,
    homeY: 470,
    workX: 205,
    workY: 390,
    facing: "left",
  },
  "offer-architect": {
    homeX: 610,
    homeY: 330,
    workX: 590,
    workY: 260,
    facing: "left",
  },
  "asset-studio": {
    homeX: 620,
    homeY: 720,
    workX: 455,
    workY: 790,
    facing: "left",
  },
  "evidence-checker": {
    homeX: 815,
    homeY: 360,
    workX: 950,
    workY: 390,
    facing: "right",
  },
  "data-inspector": {
    homeX: 820,
    homeY: 760,
    workX: 1080,
    workY: 840,
    facing: "right",
  },
};

export const ORIGINAL_OFFICE_POIS = [
  { name: "command-corridor", x: 610, y: 450 },
  { name: "strategy-door", x: 820, y: 410 },
  { name: "studio-door", x: 620, y: 690 },
  { name: "analytics-door", x: 830, y: 700 },
  { name: "south-corridor", x: 720, y: 850 },
  { name: "north-corridor", x: 790, y: 260 },
];

export function originalCharacterPath(actorId: WarRoomActorId) {
  return `/war-room-original/characters/${actorId}.png`;
}

export function pointTouchesOfficeCollision(x: number, y: number, padding = 0) {
  return ORIGINAL_OFFICE_COLLISIONS.some(
    (rect) =>
      x >= rect.x - padding &&
      x <= rect.x + rect.width + padding &&
      y >= rect.y - padding &&
      y <= rect.y + rect.height + padding,
  );
}
