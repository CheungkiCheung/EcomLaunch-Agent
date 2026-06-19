"use client";

import Image from "next/image";

import type { LaunchCrewAgent } from "./launch-crew-activity-model";
import { WAR_ROOM_PROPS, warRoomCharacterSprite } from "./war-room-assets";
import type { WarRoomAgentMotion } from "./war-room-motion";
import { WAR_ROOM_WAYPOINTS } from "./war-room-motion";

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

      <div className="absolute inset-0 z-20" aria-label="Fixed war room props">
        {WAR_ROOM_PROPS.map((prop) => {
          const waypoint = WAR_ROOM_WAYPOINTS[prop.waypoint];
          return (
            <Image
              key={prop.id}
              src={prop.src}
              alt=""
              width={prop.width}
              height={prop.height}
              data-war-room-prop={prop.id}
              data-war-room-waypoint={prop.waypoint}
              className="absolute -translate-x-1/2 -translate-y-full object-contain [image-rendering:pixelated]"
              style={{
                left: `${waypoint.x}%`,
                top: `${waypoint.y}%`,
                marginLeft: prop.offsetX,
                marginTop: prop.offsetY,
                zIndex: Math.round(waypoint.y * 10) - 30,
              }}
              unoptimized
            />
          );
        })}
      </div>

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

      {agents.map((agent) => {
        const motion = motionByAgent.get(agent.id);
        if (!motion) return null;
        const sprite = warRoomCharacterSprite(agent, motion);
        const selected = selectedAgentId === agent.id;
        return (
          <button
            key={agent.id}
            type="button"
            aria-label={`Select ${agent.name}`}
            data-war-room-agent={agent.id}
            data-war-room-character={agent.id}
            data-war-room-standalone-character={String(sprite.standalone)}
            data-war-room-sprite-frame={sprite.frame}
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
              src={sprite.src}
              alt=""
              width={sprite.width}
              height={sprite.height}
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
