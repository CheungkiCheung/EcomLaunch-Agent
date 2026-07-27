import type { CommerceCollaborationStation } from "@/core/commerce/collaboration-scene-view-model";

export const COMMERCE_COLLABORATION_ROOM_SPRITE =
  "/commerce/collaboration/commerce-room-v1.png";

const ACTOR_SPRITES = {
  explore: "/commerce/collaboration/actors/explore-v1.png",
  analyst: "/commerce/collaboration/actors/analyst-v1.png",
  verifier: "/commerce/collaboration/actors/verifier-v1.png",
  operator: "/commerce/collaboration/actors/operator-v1.png",
} as const;

const STATION_SPRITES = {
  intake: "/commerce/collaboration/stations/intake-v1.png",
  analysis: "/commerce/collaboration/stations/analysis-v1.png",
  verification: "/commerce/collaboration/stations/verification-v1.png",
  recovery: "/commerce/collaboration/stations/recovery-v1.png",
} as const;

export function commerceActorSprite(profile: string): string {
  return (
    ACTOR_SPRITES[profile as keyof typeof ACTOR_SPRITES] ??
    ACTOR_SPRITES.operator
  );
}

export function commerceStationSprite(
  station: CommerceCollaborationStation,
): string {
  if (station === "intake") return STATION_SPRITES.intake;
  if (station === "analysis") return STATION_SPRITES.analysis;
  if (station === "verification") return STATION_SPRITES.verification;
  return STATION_SPRITES.recovery;
}

export function commerceActorPlacement(
  index: number,
  total: number,
  _placementKey: string,
): { left: number; top: number } {
  if (total <= 1) return { left: 50, top: 47 };
  if (total === 2) {
    return (
      [
        { left: 30, top: 47 },
        { left: 70, top: 47 },
      ][index] ?? { left: 50, top: 47 }
    );
  }
  if (total === 3) {
    return (
      [
        { left: 22, top: 47 },
        { left: 50, top: 47 },
        { left: 78, top: 47 },
      ][index] ?? { left: 50, top: 47 }
    );
  }
  if (total === 4) {
    return (
      [
        { left: 28, top: 26 },
        { left: 72, top: 26 },
        { left: 28, top: 64 },
        { left: 72, top: 64 },
      ][index] ?? { left: 50, top: 47 }
    );
  }
  if (total <= 6) {
    return (
      [
        { left: 18, top: 26 },
        { left: 50, top: 26 },
        { left: 82, top: 26 },
        { left: 18, top: 64 },
        { left: 50, top: 64 },
        { left: 82, top: 64 },
      ][index] ?? { left: 50, top: 47 }
    );
  }

  const columns = 4;
  const rows = Math.max(2, Math.ceil(total / columns));
  const column = index % columns;
  const row = Math.floor(index / columns);
  return {
    left: 14 + column * 24,
    top: rows === 1 ? 47 : 20 + (Math.min(row, rows - 1) * 50) / (rows - 1),
  };
}
