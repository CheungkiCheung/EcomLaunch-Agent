"use client";

import { useEffect, useRef, useState } from "react";

import type { Translations } from "@/core/i18n/locales/types";

import type { ActorView, WarRoomGameHandle } from "./office-scene";
import type { WarRoomActorId, WarRoomSnapshot } from "./types";

export function WarRoomCanvas({
  snapshot,
  onActorSelect,
  labels,
}: {
  snapshot: WarRoomSnapshot;
  onActorSelect: (actorId: WarRoomActorId, view?: ActorView) => void;
  labels: Translations["warRoom"];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<WarRoomGameHandle | null>(null);
  const initialSnapshotRef = useRef(snapshot);
  const onActorSelectRef = useRef(onActorSelect);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showControls, setShowControls] = useState(true);
  initialSnapshotRef.current = snapshot;

  useEffect(() => {
    onActorSelectRef.current = onActorSelect;
  }, [onActorSelect]);

  useEffect(() => {
    let mounted = true;
    let createdGame: WarRoomGameHandle | null = null;
    const container = containerRef.current;
    if (!container) return;
    setReady(false);
    setError(null);

    void import("./office-scene")
      .then(async ({ createWarRoomGame }) => {
        if (!mounted) return;
        const game = await createWarRoomGame({
          parent: container,
          initialSnapshot: initialSnapshotRef.current,
          onActorSelect: (actorId, view) =>
            onActorSelectRef.current(actorId, view),
          labels,
        });
        if (!mounted) {
          game.destroy();
          return;
        }
        createdGame = game;
        gameRef.current = game;
        setReady(true);
        setError(null);
      })
      .catch((cause: unknown) => {
        console.error("Failed to create the War Room scene", cause);
        if (!mounted) return;
        setError(
          cause instanceof Error
            ? cause.message
            : labels.canvas.initializationFailed,
        );
      });

    return () => {
      mounted = false;
      createdGame?.destroy();
      if (gameRef.current === createdGame) {
        gameRef.current = null;
      }
      container.replaceChildren();
    };
  }, [labels]);

  useEffect(() => {
    gameRef.current?.updateSnapshot(snapshot);
  }, [snapshot]);

  useEffect(() => {
    const hideControls = (event: KeyboardEvent) => {
      if (
        [
          "ArrowUp",
          "ArrowDown",
          "ArrowLeft",
          "ArrowRight",
          "w",
          "a",
          "s",
          "d",
          "W",
          "A",
          "S",
          "D",
          "e",
          "E",
        ].includes(event.key)
      ) {
        setShowControls(false);
      }
    };
    const timer = window.setTimeout(() => setShowControls(false), 7000);
    window.addEventListener("keydown", hideControls);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", hideControls);
    };
  }, []);

  return (
    <div className="relative size-full overflow-hidden bg-[#f8f4ec]">
      <div ref={containerRef} className="absolute inset-0" />
      {!ready && (
        <div className="absolute inset-0 grid place-items-center bg-[#f8f4ec] px-6 text-center text-sm text-stone-400">
          {error ? labels.canvas.loadFailed(error) : labels.canvas.loading}
        </div>
      )}
      {showControls && (
        <div className="pointer-events-none absolute bottom-2 left-1/2 z-40 -translate-x-1/2 rounded-lg bg-black/45 px-2.5 py-1 text-[10px] whitespace-nowrap text-white/75 shadow-sm backdrop-blur transition-opacity">
          {labels.canvas.controls}
        </div>
      )}
    </div>
  );
}
