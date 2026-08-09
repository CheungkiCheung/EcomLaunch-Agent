"use client";

import {
  FastForwardIcon,
  HistoryIcon,
  PauseIcon,
  PlayIcon,
  RadioIcon,
  RewindIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

import type { WarRoomReplay, WarRoomTeam } from "./types";

type ReplayLabels = {
  title: string;
  latestRun: string;
  live: string;
  start: string;
  pause: string;
  resume: string;
  previous: string;
  next: string;
  backToLive: string;
  speed: string;
  eventOf: (current: number, total: number) => string;
  launchTeam: string;
  growthAnalyst: string;
};

export function RunReplayPanel({
  replay,
  replays,
  index,
  playing,
  speed,
  labels,
  onStart,
  onToggle,
  onPrevious,
  onNext,
  onLive,
  onReplayChange,
  onSpeedChange,
}: {
  replay: WarRoomReplay;
  replays: WarRoomReplay[];
  index: number | null;
  playing: boolean;
  speed: 1 | 2 | 4;
  labels: ReplayLabels;
  onStart: () => void;
  onToggle: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onLive: () => void;
  onReplayChange: (team: WarRoomTeam) => void;
  onSpeedChange: (speed: 1 | 2 | 4) => void;
}) {
  const event = index === null ? replay.events.at(-1) : replay.events[index];
  const isLive = index === null;
  const current = index === null ? replay.events.length : index + 1;
  const canPrevious = index !== null && index > 0;
  const canNext = index !== null && index < replay.events.length - 1;
  const isGrowth = replay.team === "data-inspector";
  const teamLabel = (team: WarRoomTeam) =>
    team === "data-inspector" ? labels.growthAnalyst : labels.launchTeam;

  return (
    <section
      className="pointer-events-auto absolute right-3 bottom-3 left-3 z-30 overflow-hidden rounded-2xl border border-[#5c4b3d]/80 bg-[#29251f]/95 text-[#f6ead6] shadow-[0_10px_30px_rgba(47,34,21,0.32)] backdrop-blur-md sm:right-4 sm:bottom-4 sm:left-4"
      data-testid="war-room-replay"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-white/10 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <div
            className={cn(
              "flex size-7 shrink-0 items-center justify-center rounded-lg",
              isGrowth
                ? "bg-teal-300/20 text-teal-100"
                : "bg-orange-400/20 text-orange-200",
            )}
          >
            <HistoryIcon className="size-3.5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[11px] font-semibold">{labels.title}</p>
            <p className="truncate text-[9px] text-[#b9a993]">
              {replay.title || labels.latestRun}
            </p>
          </div>
        </div>
        <div
          className="flex items-center rounded-lg border border-white/10 bg-black/10 p-0.5"
          data-testid="war-room-replay-sources"
        >
          {replays.map((candidate) => (
            <button
              key={candidate.team}
              type="button"
              onClick={() => onReplayChange(candidate.team)}
              aria-pressed={candidate.team === replay.team}
              className={cn(
                "rounded-md px-2 py-1 text-[9px] font-medium transition",
                candidate.team === replay.team
                  ? candidate.team === "data-inspector"
                    ? "bg-teal-300/20 text-teal-100"
                    : "bg-orange-300/20 text-orange-100"
                  : "text-[#9e907d] hover:bg-white/5 hover:text-white",
              )}
            >
              {teamLabel(candidate.team)}
            </button>
          ))}
        </div>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[9px] font-medium",
            isLive
              ? "border-emerald-300/30 bg-emerald-300/10 text-emerald-200"
              : "border-orange-300/30 bg-orange-300/10 text-orange-200",
          )}
        >
          {isLive ? labels.live : labels.eventOf(current, replay.events.length)}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={onPrevious}
            disabled={!canPrevious}
            className="flex size-7 items-center justify-center rounded-md text-[#b9a993] transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
            aria-label={labels.previous}
            title={labels.previous}
          >
            <RewindIcon className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={index === null ? onStart : onToggle}
            className={cn(
              "flex size-8 items-center justify-center rounded-lg text-[#38291c] transition",
              isGrowth
                ? "bg-teal-300 hover:bg-teal-200"
                : "bg-orange-400 hover:bg-orange-300",
            )}
            aria-label={
              index === null
                ? labels.start
                : playing
                  ? labels.pause
                  : labels.resume
            }
            title={
              index === null
                ? labels.start
                : playing
                  ? labels.pause
                  : labels.resume
            }
          >
            {index === null ? (
              <PlayIcon className="size-3.5 fill-current" />
            ) : playing ? (
              <PauseIcon className="size-3.5 fill-current" />
            ) : (
              <PlayIcon className="size-3.5 fill-current" />
            )}
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNext}
            className="flex size-7 items-center justify-center rounded-md text-[#b9a993] transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
            aria-label={labels.next}
            title={labels.next}
          >
            <FastForwardIcon className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={onLive}
            disabled={isLive}
            className="ml-1 flex items-center gap-1 rounded-md px-2 py-1 text-[9px] text-[#b9a993] transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
            aria-label={labels.backToLive}
            title={labels.backToLive}
          >
            <RadioIcon className="size-3" />
            <span className="hidden sm:inline">{labels.live}</span>
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 py-2">
        <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-white/10">
          <div
            className={cn(
              "h-full rounded-full bg-gradient-to-r transition-[width] duration-300",
              isGrowth
                ? "from-teal-300 to-cyan-300"
                : "from-orange-300 to-rose-300",
            )}
            style={{ width: `${(current / replay.events.length) * 100}%` }}
          />
        </div>
        <label className="flex shrink-0 items-center gap-1 text-[9px] text-[#b9a993]">
          <span className="sr-only">{labels.speed}</span>
          <select
            value={speed}
            onChange={(event) =>
              onSpeedChange(Number(event.target.value) as 1 | 2 | 4)
            }
            aria-label={labels.speed}
            className="rounded border border-white/10 bg-white/5 px-1.5 py-1 text-[9px] text-[#f6ead6] outline-none"
          >
            {[1, 2, 4].map((value) => (
              <option key={value} value={value} className="bg-[#29251f]">
                {value}×
              </option>
            ))}
          </select>
        </label>
      </div>

      {event && (
        <div className="border-t border-white/10 px-3 py-2">
          <p
            className={cn(
              "truncate text-[10px] font-semibold",
              isGrowth ? "text-teal-100" : "text-orange-100",
            )}
            data-testid="war-room-replay-event-title"
          >
            {event.title}
          </p>
          {event.detail && (
            <p className="mt-0.5 line-clamp-2 text-[10px] leading-4 text-[#b9a993]">
              {event.detail}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
