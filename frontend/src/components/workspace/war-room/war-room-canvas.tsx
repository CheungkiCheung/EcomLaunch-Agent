"use client";

import { useEffect, useRef, useState } from "react";

import type { WarRoomGameHandle } from "./scene";
import type { WarRoomActorId, WarRoomSnapshot } from "./types";

export function WarRoomCanvas({
  snapshot,
  onActorSelect,
}: {
  snapshot: WarRoomSnapshot;
  onActorSelect: (actorId: WarRoomActorId) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<WarRoomGameHandle | null>(null);
  const initialSnapshotRef = useRef(snapshot);
  const onActorSelectRef = useRef(onActorSelect);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onActorSelectRef.current = onActorSelect;
  }, [onActorSelect]);

  useEffect(() => {
    let mounted = true;
    let createdGame: WarRoomGameHandle | null = null;
    const container = containerRef.current;
    if (!container) return;

    void import("./scene").then(async ({ createWarRoomGame }) => {
      // React Strict Mode mounts, cleans up, and mounts effects again in
      // development. Avoid starting a stale Phaser instance after that cleanup.
      if (!mounted) return;
      const game = await createWarRoomGame({
        parent: container,
        initialSnapshot: initialSnapshotRef.current,
        onActorSelect: (actorId) => onActorSelectRef.current(actorId),
      });
      if (!mounted) {
        game.destroy();
        return;
      }
      createdGame = game;
      gameRef.current = game;
      setReady(true);
    });

    return () => {
      mounted = false;
      createdGame?.destroy();
      if (gameRef.current === createdGame) {
        gameRef.current = null;
      }
      // Phaser normally removes its canvas during destroy. Clearing this
      // effect-owned container also covers an instance torn down while booting.
      container.replaceChildren();
    };
  }, []);

  useEffect(() => {
    gameRef.current?.updateSnapshot(snapshot);
  }, [snapshot]);

  return (
    <div className="relative size-full overflow-hidden bg-[#f7f3eb]">
      <div ref={containerRef} className="absolute inset-0" />
      {!ready && (
        <div className="absolute inset-0 grid place-items-center bg-[#f7f3eb] text-sm text-stone-500">
          正在布置作战室…
        </div>
      )}
    </div>
  );
}
