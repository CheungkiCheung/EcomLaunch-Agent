"use client";

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import type { StoreCrewAgent, StoreCrewRole } from "./store-crew-activity";
import {
  STORE_HOME_POINTS,
  targetPointForAgent,
  walkingFrame,
  type StoreRoomPoint,
} from "./store-war-room-motion";

const CHARACTER_ASSETS: Record<
  StoreCrewRole,
  { sourceRole: string; width: number; name: string }
> = {
  lead: { sourceRole: "launch-director", width: 6, name: "经营主理人" },
  explore: {
    sourceRole: "market-voc-researcher",
    width: 4.9,
    name: "数据侦察员",
  },
  analyst: { sourceRole: "growth-analyst", width: 5.2, name: "经营分析师" },
  verifier: { sourceRole: "evidence-checker", width: 4.9, name: "证据核验员" },
};

function spriteUrl(
  role: StoreCrewRole,
  frame: "idle" | "work" | "walk-left" | "walk-right" | "walk-up" | "walk-down",
) {
  const source = CHARACTER_ASSETS[role].sourceRole;
  const resolvedFrame =
    role === "lead" ? (frame === "work" ? "work" : "idle") : frame;
  return `/images/ecom-launch/war-room/agents/${source}/${resolvedFrame}.png`;
}

export function StoreWarRoomStage({
  agents,
  selectedRole,
  onSelectRole,
}: {
  agents: StoreCrewAgent[];
  selectedRole: StoreCrewRole;
  onSelectRole: (role: StoreCrewRole) => void;
}) {
  const reducedMotion = useReducedMotion();
  const [tick, setTick] = useState(0);
  const [arrived, setArrived] = useState<Set<StoreCrewRole>>(
    () => new Set(["lead"]),
  );
  const previousTargets = useRef<Record<StoreCrewRole, StoreRoomPoint>>({
    lead: STORE_HOME_POINTS.lead,
    explore: targetPointForAgent({ id: "explore", active: false }, 0),
    analyst: targetPointForAgent({ id: "analyst", active: false }, 0),
    verifier: targetPointForAgent({ id: "verifier", active: false }, 0),
  });

  useEffect(() => {
    if (reducedMotion) return;
    const id = window.setInterval(() => setTick((value) => value + 1), 4200);
    return () => window.clearInterval(id);
  }, [reducedMotion]);

  useEffect(() => {
    setArrived((current) => {
      const next = new Set(current);
      for (const agent of agents) {
        if (!agent.active || agent.id === "lead") {
          if (agent.id !== "lead") next.delete(agent.id);
          continue;
        }
        const previous = previousTargets.current[agent.id];
        const home = STORE_HOME_POINTS[agent.id];
        if (previous.x === home.x && previous.y === home.y) {
          next.add(agent.id);
        } else {
          next.delete(agent.id);
        }
      }
      return next;
    });
  }, [agents]);

  const rendered = useMemo(
    () =>
      agents.map((agent) => ({
        agent,
        target: reducedMotion
          ? STORE_HOME_POINTS[agent.id]
          : targetPointForAgent(agent, tick),
      })),
    [agents, reducedMotion, tick],
  );

  return (
    <div
      className="relative aspect-[1672/941] w-full overflow-hidden rounded-lg bg-[#efe4d4] shadow-[0_24px_80px_rgba(76,57,38,0.16)]"
      data-store-war-room-stage
    >
      {/* Generated with the built-in image generation tool; runtime actors are separate. */}
      <img
        src="/images/store-operator/war-room/background-v1.png"
        alt="商铺运营作战室"
        className="absolute inset-0 size-full object-cover"
      />

      {rendered.map(({ agent, target }) => {
        const previous = previousTargets.current[agent.id];
        const isWorking =
          agent.active && (agent.id === "lead" || arrived.has(agent.id));
        const frame = isWorking
          ? "work"
          : agent.id === "lead"
            ? "idle"
            : walkingFrame(previous, target);
        const asset = CHARACTER_ASSETS[agent.id];
        return (
          <motion.button
            key={agent.id}
            type="button"
            aria-label={`${asset.name}：${agent.lastLine}`}
            className={cn(
              "group absolute -translate-x-1/2 -translate-y-full border-0 bg-transparent p-0 outline-none",
              "focus-visible:ring-primary rounded-xl focus-visible:ring-2 focus-visible:ring-offset-2",
            )}
            initial={false}
            animate={{ left: `${target.x}%`, top: `${target.y}%` }}
            transition={
              reducedMotion
                ? { duration: 0 }
                : { duration: agent.active ? 1.45 : 2.8, ease: "easeInOut" }
            }
            onAnimationComplete={() => {
              previousTargets.current[agent.id] = target;
              if (agent.active) {
                setArrived((current) => new Set(current).add(agent.id));
              }
            }}
            onClick={() => onSelectRole(agent.id)}
            data-store-agent={agent.id}
            data-store-agent-active={String(agent.active)}
            data-store-agent-motion={
              isWorking
                ? "working"
                : agent.active
                  ? "returning_home"
                  : "roaming"
            }
            style={{
              width: `${asset.width}%`,
              zIndex: Math.round(target.y * 10),
            }}
          >
            {agent.active && (
              <span className="absolute right-1/2 -bottom-1 h-3 w-12 translate-x-1/2 rounded-full bg-teal-400/30 blur-sm" />
            )}
            <img
              src={spriteUrl(agent.id, frame)}
              alt=""
              className="relative h-auto w-full object-contain drop-shadow-[0_8px_5px_rgba(60,45,30,0.2)]"
              draggable={false}
            />
            <span
              data-store-agent-label={agent.id}
              className={cn(
                "absolute top-full left-1/2 mt-1 -translate-x-1/2 rounded-full border px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shadow-sm backdrop-blur",
                selectedRole === agent.id
                  ? "border-teal-500/40 bg-teal-50/95 text-teal-800"
                  : "hidden border-white/70 bg-white/85 text-slate-700 sm:block",
              )}
            >
              {asset.name}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
