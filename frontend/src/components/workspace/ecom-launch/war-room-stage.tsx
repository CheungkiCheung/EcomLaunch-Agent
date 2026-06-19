"use client";

import Image from "next/image";

import type { LaunchCrewAgent } from "./launch-crew-activity-model";
import { frameForAgent } from "./pixel-office";
import type { WarRoomAgentMotion } from "./war-room-motion";

const SPRITE_SIZES: Record<
  LaunchCrewAgent["id"],
  { width: number; height: number }
> = {
  "market-voc-researcher": { width: 118, height: 104 },
  "offer-architect": { width: 118, height: 110 },
  "launch-director": { width: 170, height: 142 },
  "evidence-checker": { width: 116, height: 116 },
  "growth-analyst": { width: 114, height: 114 },
  "asset-studio": { width: 118, height: 74 },
};

function spritePath(agent: LaunchCrewAgent) {
  const frame = frameForAgent(agent);
  if (agent.id === "launch-director") {
    return `/images/ecom-launch/sprites/launch-director/${frame}.png`;
  }
  const normalizedFrame =
    frame === "complete" ? "talking" : frame === "error" ? "idle" : frame;
  return `/images/ecom-launch/sprites/agents/${agent.id}/${normalizedFrame}.png`;
}

function pointStyle(point: { x: number; y: number }) {
  return {
    left: `${point.x}%`,
    top: `${point.y}%`,
  };
}

export function WarRoomStage({
  agents,
  motions,
  selectedAgentId,
  onSelectAgent,
}: {
  agents: LaunchCrewAgent[];
  motions: WarRoomAgentMotion[];
  selectedAgentId: LaunchCrewAgent["id"];
  onSelectAgent: (id: LaunchCrewAgent["id"]) => void;
}) {
  const motionByAgent = new Map(motions.map((motion) => [motion.id, motion]));

  return (
    <section
      aria-label="Animated EcomLaunch war room"
      className="relative size-full overflow-hidden bg-[#223038]"
    >
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.055)_1px,transparent_1px),linear-gradient(0deg,rgba(255,255,255,0.055)_1px,transparent_1px)] bg-[size:32px_32px]" />
      <div className="absolute inset-x-0 top-0 h-[15%] border-b-4 border-[#101716] bg-[#3a464d] shadow-[inset_0_-18px_0_rgba(0,0,0,0.14)]" />
      <div className="absolute top-[3%] left-[24%] h-[7%] w-[52%] border-4 border-[#151e20] bg-[#a8bbc0]/18 shadow-[inset_0_0_0_3px_rgba(255,255,255,0.07)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_48%,rgba(5,9,10,0.48)_100%)]" />

      <svg
        className="pointer-events-none absolute inset-0 z-10 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {motions
          .filter((motion) => motion.id !== "launch-director")
          .map((motion) => (
            <line
              key={motion.id}
              x1={motion.position.x}
              y1={motion.position.y}
              x2={50}
              y2={44}
              stroke="#78ffd4"
              strokeWidth={motion.state === "roaming" ? "0.22" : "0.52"}
              strokeLinecap="round"
              opacity={motion.state === "roaming" ? 0.24 : 0.78}
            />
          ))}
      </svg>

      <div className="absolute top-[18%] left-[41%] z-20 h-[23%] w-[18%] border-4 border-[#101716] bg-[#25363a] shadow-[0_0_32px_rgba(110,255,207,0.18)]">
        <div className="absolute inset-3 bg-[#102126]">
          <div className="absolute top-[20%] left-[18%] h-[28%] w-[36%] bg-cyan-300/70" />
          <div className="absolute right-[12%] bottom-[18%] h-[32%] w-[42%] bg-emerald-300/45" />
        </div>
      </div>

      {agents.map((agent) => {
        const motion = motionByAgent.get(agent.id);
        if (!motion) return null;
        const size = SPRITE_SIZES[agent.id];
        const selected = selectedAgentId === agent.id;
        return (
          <button
            key={agent.id}
            type="button"
            aria-label={`Select ${agent.name}`}
            data-war-room-agent={agent.id}
            data-motion-state={motion.state}
            className="group absolute z-30 -translate-x-1/2 -translate-y-full text-left transition-[left,top,transform] duration-700 ease-out focus-visible:outline-none"
            style={{
              ...pointStyle(motion.position),
              zIndex: Math.round(motion.position.y * 10),
            }}
            onClick={() => onSelectAgent(agent.id)}
          >
            <span
              className={[
                "pointer-events-none absolute top-full left-1/2 h-4 w-24 -translate-x-1/2 -translate-y-3 rounded-full bg-cyan-200/10 blur-md transition-opacity",
                selected ? "opacity-100" : "opacity-0 group-hover:opacity-80",
              ].join(" ")}
            />
            {selected && (
              <span className="pointer-events-none absolute top-full left-1/2 h-8 w-28 -translate-x-1/2 -translate-y-5 rounded-full border-2 border-cyan-200/90 shadow-[0_0_18px_rgba(103,255,214,0.45)]" />
            )}
            <Image
              src={spritePath(agent)}
              alt=""
              width={size.width}
              height={size.height}
              className={[
                "relative z-10 object-contain [image-rendering:pixelated]",
                motion.state === "roaming" ? "animate-pulse" : "",
              ].join(" ")}
              priority={agent.id === "launch-director"}
              unoptimized
            />
            <span className="absolute top-full left-1/2 z-20 mt-3 -translate-x-1/2 rounded border border-cyan-100/20 bg-[#101714]/90 px-2 py-1 text-[10px] font-black whitespace-nowrap text-cyan-50 shadow-[2px_2px_0_rgba(0,0,0,0.58)]">
              {agent.shortName}
            </span>
          </button>
        );
      })}

      <div className="pointer-events-none absolute top-5 left-5 z-50 rounded border border-cyan-100/25 bg-[#101714]/88 px-3 py-2 text-cyan-50 shadow-[3px_3px_0_rgba(0,0,0,0.62)]">
        <div className="text-[10px] font-black tracking-[0.2em] text-cyan-100/70 uppercase">
          Launch War Room
        </div>
        <div className="mt-1 text-xs font-black">
          Director locked on station
        </div>
      </div>
    </section>
  );
}
