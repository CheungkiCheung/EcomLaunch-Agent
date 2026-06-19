"use client";

import {
  CheckIcon,
  CircleDashedIcon,
  Loader2Icon,
  TriangleAlertIcon,
} from "lucide-react";
import Image from "next/image";

import { cn } from "@/lib/utils";

import {
  type LaunchCrewAgent,
  type LaunchCrewAgentStatus,
  type LaunchCrewRole,
} from "./launch-crew-activity-model";

type PixelOfficeProps = {
  agents: LaunchCrewAgent[];
  className?: string;
  onSelectAgent?: (role: LaunchCrewRole) => void;
};

type AgentStationConfig = {
  stationClassName: string;
  deskTone: string;
  monitorTone: string;
  characterTone: string;
  hairTone: string;
  accessory: "cap" | "glasses" | "ponytail" | "none";
  screen: "bars" | "grid" | "map" | "docs" | "chart" | "palette";
  mirror?: boolean;
  sprite?: SpriteConfig;
};

export type AgentFrame = "idle" | "working" | "talking" | "complete" | "error";

type SpriteConfig = {
  frames: Record<AgentFrame, string>;
  width: number;
  height: number;
};

function spriteFrames(role: Exclude<LaunchCrewRole, "launch-director">) {
  const base = `/images/ecom-launch/sprites/agents/${role}`;
  return {
    idle: `${base}/idle.png`,
    working: `${base}/working.png`,
    talking: `${base}/talking.png`,
    complete: `${base}/talking.png`,
    error: `${base}/idle.png`,
  } satisfies Record<AgentFrame, string>;
}

const STATION_CONFIGS: Record<LaunchCrewRole, AgentStationConfig> = {
  "market-voc-researcher": {
    stationClassName: "left-[3%] top-[15%]",
    deskTone: "bg-[#8b6a46]",
    monitorTone: "bg-cyan-300",
    characterTone: "bg-sky-500",
    hairTone: "bg-[#143c56]",
    accessory: "cap",
    screen: "bars",
    sprite: {
      frames: spriteFrames("market-voc-researcher"),
      width: 118,
      height: 104,
    },
  },
  "offer-architect": {
    stationClassName: "left-[3%] bottom-[13%]",
    deskTone: "bg-[#7b5e3e]",
    monitorTone: "bg-emerald-300",
    characterTone: "bg-emerald-500",
    hairTone: "bg-[#194a31]",
    accessory: "cap",
    screen: "grid",
    sprite: {
      frames: spriteFrames("offer-architect"),
      width: 118,
      height: 110,
    },
  },
  "launch-director": {
    stationClassName: "left-1/2 top-[39%] -translate-x-1/2 -translate-y-1/2",
    deskTone: "bg-[#46524d]",
    monitorTone: "bg-cyan-300",
    characterTone: "bg-blue-500",
    hairTone: "bg-[#8b542b]",
    accessory: "none",
    screen: "map",
    sprite: {
      frames: {
        idle: "/images/ecom-launch/sprites/launch-director/idle.png",
        working: "/images/ecom-launch/sprites/launch-director/working.png",
        talking: "/images/ecom-launch/sprites/launch-director/talking.png",
        complete: "/images/ecom-launch/sprites/launch-director/complete.png",
        error: "/images/ecom-launch/sprites/launch-director/error.png",
      },
      width: 170,
      height: 142,
    },
  },
  "evidence-checker": {
    stationClassName: "right-[3%] top-[15%]",
    deskTone: "bg-[#8b6a46]",
    monitorTone: "bg-blue-300",
    characterTone: "bg-blue-500",
    hairTone: "bg-[#151b20]",
    accessory: "glasses",
    screen: "docs",
    mirror: true,
    sprite: {
      frames: spriteFrames("evidence-checker"),
      width: 116,
      height: 116,
    },
  },
  "growth-analyst": {
    stationClassName: "left-1/2 bottom-[1%] -translate-x-1/2",
    deskTone: "bg-[#7f6a42]",
    monitorTone: "bg-amber-300",
    characterTone: "bg-amber-500",
    hairTone: "bg-[#7a4a28]",
    accessory: "none",
    screen: "chart",
    sprite: {
      frames: spriteFrames("growth-analyst"),
      width: 114,
      height: 114,
    },
  },
  "asset-studio": {
    stationClassName: "right-[3%] bottom-[13%]",
    deskTone: "bg-[#8b6a46]",
    monitorTone: "bg-rose-300",
    characterTone: "bg-rose-500",
    hairTone: "bg-[#d94f8f]",
    accessory: "ponytail",
    screen: "palette",
    mirror: true,
    sprite: {
      frames: spriteFrames("asset-studio"),
      width: 118,
      height: 74,
    },
  },
};

const STATUS_COPY: Record<LaunchCrewAgentStatus, string> = {
  idle: "待命",
  working: "行动中",
  searching: "搜索中",
  reading: "阅读中",
  writing: "写作中",
  done: "已回传",
  delivered: "已回传",
  error: "阻塞",
};

const STATUS_TONE: Record<LaunchCrewAgentStatus, string> = {
  idle: "border-slate-300 bg-slate-100 text-slate-700",
  working: "border-cyan-400 bg-cyan-100 text-cyan-950",
  searching: "border-cyan-400 bg-cyan-100 text-cyan-950",
  reading: "border-cyan-400 bg-cyan-100 text-cyan-950",
  writing: "border-cyan-400 bg-cyan-100 text-cyan-950",
  done: "border-emerald-400 bg-emerald-100 text-emerald-950",
  delivered: "border-emerald-400 bg-emerald-100 text-emerald-950",
  error: "border-red-400 bg-red-100 text-red-950",
};

function isBusy(status: LaunchCrewAgentStatus) {
  return (
    status === "working" ||
    status === "searching" ||
    status === "reading" ||
    status === "writing"
  );
}

export function frameForAgent(
  agent: Pick<LaunchCrewAgent, "status" | "selected">,
): AgentFrame {
  if (agent.status === "error") {
    return "error";
  }
  if (isBusy(agent.status)) {
    return "working";
  }
  if (agent.status === "done" || agent.status === "delivered") {
    return "complete";
  }
  if (agent.selected) {
    return "talking";
  }
  return "idle";
}

function lineForAgent(agent: LaunchCrewAgent) {
  return agent.currentAction ?? agent.lastLine;
}

function StatusIcon({ status }: { status: LaunchCrewAgentStatus }) {
  if (status === "done" || status === "delivered") {
    return <CheckIcon className="size-3" />;
  }
  if (status === "error") {
    return <TriangleAlertIcon className="size-3" />;
  }
  if (isBusy(status)) {
    return <Loader2Icon className="size-3 animate-spin" />;
  }
  return <CircleDashedIcon className="size-3" />;
}

function PixelRoom({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative h-[350px] overflow-hidden bg-[#25313a] 2xl:h-[382px]">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.055)_1px,transparent_1px),linear-gradient(0deg,rgba(255,255,255,0.055)_1px,transparent_1px)] bg-[size:24px_24px]" />
      <div className="absolute inset-x-0 top-0 h-16 border-b-4 border-[#171d20] bg-[#38434b] shadow-[inset_0_-12px_0_rgba(0,0,0,0.12)]" />
      <div className="absolute inset-x-12 top-3 h-9 border-4 border-[#192024] bg-[#9fb2b8]/20 shadow-[inset_0_0_0_3px_rgba(255,255,255,0.08)]" />
      <div className="absolute top-4 left-8 h-12 w-20 border-4 border-[#171d20] bg-[#2b3a40]">
        <MiniScreen variant="bars" tone="bg-cyan-300" />
      </div>
      <div className="absolute top-4 right-8 h-12 w-20 border-4 border-[#171d20] bg-[#2b3a40]">
        <MiniScreen variant="docs" tone="bg-blue-300" />
      </div>
      <RoomPlant className="top-[62px] left-4" />
      <RoomPlant className="right-5 bottom-8" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_42%,rgba(8,11,12,0.45)_100%)]" />
      {children}
      <div className="pointer-events-none absolute inset-0 rounded-lg shadow-[inset_0_0_0_4px_rgba(15,23,18,0.55),inset_0_-18px_0_rgba(0,0,0,0.18)]" />
    </div>
  );
}

function RoomPlant({ className }: { className?: string }) {
  return (
    <div className={cn("absolute z-[3] h-14 w-12", className)}>
      <div className="absolute bottom-0 left-3 h-5 w-6 border-2 border-[#1a211e] bg-[#8b6a46]" />
      <div className="absolute bottom-4 left-4 h-5 w-2 bg-[#2e7d4f]" />
      <div className="absolute bottom-7 left-1 h-4 w-7 rounded-full bg-[#4da866]" />
      <div className="absolute right-1 bottom-8 h-4 w-7 rounded-full bg-[#3e945a]" />
      <div className="absolute bottom-10 left-4 h-4 w-6 rounded-full bg-[#66bd73]" />
    </div>
  );
}

function MiniScreen({
  variant,
  tone,
}: {
  variant: AgentStationConfig["screen"];
  tone: string;
}) {
  return (
    <div className="absolute inset-1 overflow-hidden bg-[#152127] p-1">
      {variant === "bars" && (
        <div className="flex h-full items-end gap-1">
          {[36, 62, 48, 78, 54].map((height, index) => (
            <span
              key={index}
              className={cn("w-2 opacity-85", tone)}
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
      )}
      {variant === "grid" && (
        <div className="grid h-full grid-cols-3 gap-1">
          {Array.from({ length: 9 }).map((_, index) => (
            <span key={index} className={cn("opacity-80", tone)} />
          ))}
        </div>
      )}
      {variant === "map" && (
        <div className="relative h-full">
          <div
            className={cn("absolute top-2 left-5 h-5 w-9 opacity-80", tone)}
          />
          <div
            className={cn("absolute top-4 right-4 h-6 w-10 opacity-60", tone)}
          />
          <div
            className={cn("absolute bottom-2 left-8 h-3 w-12 opacity-70", tone)}
          />
        </div>
      )}
      {variant === "docs" && (
        <div className="space-y-1">
          <span className={cn("block h-2 w-6 opacity-90", tone)} />
          <span className={cn("block h-1 w-12 opacity-70", tone)} />
          <span className={cn("block h-1 w-10 opacity-70", tone)} />
          <span className={cn("block h-1 w-14 opacity-70", tone)} />
        </div>
      )}
      {variant === "chart" && (
        <div className="relative h-full">
          <span className="absolute bottom-3 left-2 h-px w-14 rotate-[-18deg] bg-amber-200" />
          <span
            className={cn("absolute right-4 bottom-4 size-3 opacity-90", tone)}
          />
          <span
            className={cn("absolute top-3 left-3 size-2 opacity-70", tone)}
          />
        </div>
      )}
      {variant === "palette" && (
        <div className="grid h-full grid-cols-3 gap-1">
          {[
            "bg-rose-300",
            "bg-amber-300",
            "bg-cyan-300",
            "bg-emerald-300",
            "bg-blue-300",
            "bg-fuchsia-300",
          ].map((color) => (
            <span key={color} className={color} />
          ))}
        </div>
      )}
    </div>
  );
}

function ConnectionLines({ active }: { active: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 mix-blend-screen">
      <svg
        className="size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <filter
            id="launch-crew-line-glow"
            x="-20%"
            y="-20%"
            width="140%"
            height="140%"
          >
            <feGaussianBlur stdDeviation="1.3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {[
          ["27", "31", "50", "41"],
          ["27", "65", "50", "43"],
          ["73", "31", "50", "41"],
          ["73", "65", "50", "43"],
          ["50", "78", "50", "48"],
        ].map(([x1, y1, x2, y2]) => (
          <line
            key={`${x1}-${y1}`}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#6effcf"
            strokeWidth={active ? "0.85" : "0.55"}
            strokeLinecap="round"
            filter="url(#launch-crew-line-glow)"
            opacity={active ? 0.95 : 0.5}
          />
        ))}
        {[
          ["27", "31"],
          ["27", "65"],
          ["73", "31"],
          ["73", "65"],
          ["50", "78"],
          ["50", "43"],
        ].map(([cx, cy]) => (
          <circle
            key={`${cx}-${cy}`}
            cx={cx}
            cy={cy}
            r={active ? "1.3" : "1"}
            fill="#86ffd8"
            filter="url(#launch-crew-line-glow)"
            opacity={active ? 1 : 0.72}
          />
        ))}
      </svg>
    </div>
  );
}

function PixelDesk({
  config,
  director,
}: {
  config: AgentStationConfig;
  director: boolean;
}) {
  if (director) {
    return (
      <div className="absolute top-8 left-1/2 h-[98px] w-[174px] -translate-x-1/2">
        <div className="absolute inset-x-6 top-0 h-16 border-4 border-[#111918] bg-[#203238] shadow-[0_0_18px_rgba(110,255,207,0.26)]">
          <MiniScreen variant="map" tone={config.monitorTone} />
        </div>
        <div className="absolute right-0 bottom-0 left-0 h-14 rounded-b-lg border-4 border-[#111918] bg-[#33423f] shadow-[inset_0_-8px_0_rgba(0,0,0,0.18)]" />
        <div className="absolute right-3 bottom-3 left-3 h-5 bg-[#16201f]">
          <div className="mx-auto mt-1 h-2 w-20 bg-[linear-gradient(90deg,#5df0a3_45%,#f0be4b_45%,#f0be4b_72%,#263331_72%)]" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "absolute top-0 left-0 h-[104px] w-[142px]",
        config.mirror && "-scale-x-100",
      )}
    >
      <div className="absolute top-0 left-7 h-14 w-28 border-4 border-[#151b1a] bg-[#26343a]">
        <MiniScreen variant={config.screen} tone={config.monitorTone} />
      </div>
      <div
        className={cn(
          "absolute bottom-0 left-0 h-16 w-[142px] border-4 border-[#151b1a] shadow-[inset_0_-8px_0_rgba(0,0,0,0.18)]",
          config.deskTone,
        )}
      />
      <div className="absolute bottom-2 left-11 h-3 w-12 bg-[#151b1a]" />
      <div className="absolute right-3 bottom-4 h-6 w-4 border-2 border-[#151b1a] bg-[#d8d4c8]" />
      <div className="absolute bottom-5 left-5 size-4 border-2 border-[#151b1a] bg-[#cfd6d2]" />
    </div>
  );
}

function PixelCharacter({
  config,
  frame,
  director,
}: {
  config: AgentStationConfig;
  frame: AgentFrame;
  director: boolean;
}) {
  if (config.sprite) {
    return (
      <SpriteCharacter
        config={config.sprite}
        frame={frame}
        director={director}
      />
    );
  }

  const busy = frame === "working";
  const talking = frame === "talking" || frame === "complete";
  const blocked = frame === "error";

  return (
    <div
      data-frame={frame}
      className={cn(
        "absolute z-10 h-16 w-12 transition-transform",
        director ? "top-[70px] left-1/2 -translate-x-1/2" : "top-10 left-14",
        busy && "animate-pulse",
        talking && "-translate-y-1",
        blocked && "rotate-[-3deg]",
        config.mirror && !director && "left-20 -scale-x-100",
      )}
    >
      {config.accessory === "ponytail" && (
        <div
          className={cn(
            "absolute top-2 right-0 h-8 w-5 rounded-full",
            config.hairTone,
          )}
        />
      )}
      <div className="absolute top-1 left-2 h-8 w-8 border-2 border-[#151b1a] bg-[#ffd49b]" />
      <div
        className={cn(
          "absolute top-0 left-1 h-4 w-10 border-2 border-[#151b1a]",
          config.hairTone,
        )}
      />
      {config.accessory === "cap" && (
        <div
          className={cn(
            "absolute -top-1 left-0 h-4 w-11 border-2 border-[#151b1a]",
            config.characterTone,
          )}
        />
      )}
      {config.accessory === "glasses" && (
        <div className="absolute top-4 left-[9px] flex gap-1">
          <span className="size-2 border border-[#151b1a] bg-white/20" />
          <span className="size-2 border border-[#151b1a] bg-white/20" />
        </div>
      )}
      <div className="absolute top-[18px] left-[15px] size-1 bg-[#151b1a]" />
      <div className="absolute top-[18px] right-[15px] size-1 bg-[#151b1a]" />
      <div
        className={cn(
          "absolute top-[25px] left-[18px] h-1 w-3 bg-[#151b1a]",
          talking && "h-2 rounded-b-full",
        )}
      />
      <div
        className={cn(
          "absolute top-9 left-2 h-6 w-8 border-2 border-[#151b1a]",
          config.characterTone,
        )}
      />
      <div
        className={cn(
          "absolute top-10 h-3 w-2 border-2 border-[#151b1a] bg-[#ffd49b]",
          busy
            ? "left-0 rotate-[-20deg]"
            : talking
              ? "-left-0.5 rotate-[-10deg]"
              : "left-1",
        )}
      />
      <div
        className={cn(
          "absolute top-10 h-3 w-2 border-2 border-[#151b1a] bg-[#ffd49b]",
          busy
            ? "right-0 rotate-[20deg]"
            : talking
              ? "-right-0.5 rotate-[10deg]"
              : "right-1",
        )}
      />
      {frame === "complete" && (
        <div className="absolute -top-4 -right-1 grid size-5 place-items-center border-2 border-[#151b1a] bg-emerald-400 text-[10px] font-black text-emerald-950">
          ✓
        </div>
      )}
      {blocked && (
        <div className="absolute -top-4 right-0 grid size-5 place-items-center border-2 border-[#151b1a] bg-red-400 text-[10px] font-black text-white">
          !
        </div>
      )}
    </div>
  );
}

function SpriteCharacter({
  config,
  frame,
  director,
}: {
  config: SpriteConfig;
  frame: AgentFrame;
  director: boolean;
}) {
  return (
    <Image
      src={config.frames[frame]}
      alt=""
      width={config.width}
      height={config.height}
      data-frame={frame}
      className={cn(
        "absolute z-10 object-contain [image-rendering:pixelated]",
        director
          ? "top-[18px] left-1/2 -translate-x-1/2"
          : "top-0 left-1/2 -translate-x-1/2",
      )}
      priority={director}
      unoptimized
    />
  );
}

function SpeechBubble({
  agent,
  director,
}: {
  agent: LaunchCrewAgent;
  director: boolean;
}) {
  if (!agent.active && !agent.selected) {
    return null;
  }

  return (
    <div
      className={cn(
        "absolute z-30 max-w-[138px] rounded border-2 border-[#121817] bg-[#fffdf2]/95 px-2 py-1 text-[9px] leading-3 font-bold text-[#131815] shadow-[3px_3px_0_rgba(5,10,9,0.7)]",
        director
          ? "top-[52px] left-[164px] max-w-[104px]"
          : "top-6 left-[86px]",
        agent.status === "error" && "bg-red-50 text-red-950",
        (agent.status === "done" || agent.status === "delivered") &&
          "bg-emerald-50 text-emerald-950",
      )}
    >
      <span className="line-clamp-2">{lineForAgent(agent)}</span>
      <span className="absolute -bottom-2 left-3 size-3 rotate-45 border-r-2 border-b-2 border-[#121817] bg-inherit" />
    </div>
  );
}

function StatusCard({
  agent,
  director,
}: {
  agent: LaunchCrewAgent;
  director: boolean;
}) {
  return (
    <div
      className={cn(
        "absolute z-20 rounded border-2 border-cyan-100/20 bg-[#101714]/92 px-2 py-1 text-cyan-50 shadow-[3px_3px_0_rgba(5,10,9,0.72)] backdrop-blur-sm",
        director
          ? "top-[142px] left-1/2 w-[158px] -translate-x-1/2 shadow-[0_0_18px_rgba(81,255,194,0.3),3px_3px_0_rgba(5,10,9,0.72)]"
          : "top-[122px] left-1/2 w-[118px] -translate-x-1/2",
      )}
    >
      <div className="flex min-w-0 items-center justify-between gap-1.5">
        <h3
          className="truncate text-[10px] leading-3 font-black"
          title={agent.shortName}
        >
          {agent.shortName}
        </h3>
        <span
          className={cn(
            "grid size-4 shrink-0 place-items-center rounded-full border",
            STATUS_TONE[agent.status],
            director && "border-cyan-200/40 bg-cyan-50/10 text-cyan-50",
          )}
          aria-label={STATUS_COPY[agent.status]}
          title={STATUS_COPY[agent.status]}
        >
          <StatusIcon status={agent.status} />
        </span>
      </div>
      <p className="mt-0.5 truncate text-[8px] leading-none text-cyan-100/68">
        {agent.label}
      </p>
    </div>
  );
}

function AgentStation({
  agent,
  onSelectAgent,
}: {
  agent: LaunchCrewAgent;
  onSelectAgent?: (role: LaunchCrewRole) => void;
}) {
  const config = STATION_CONFIGS[agent.id];
  const director = agent.id === "launch-director";
  const frame = frameForAgent(agent);

  return (
    <button
      type="button"
      className={cn(
        "group absolute z-20 text-left focus-visible:outline-none",
        director ? "h-[188px] w-[220px]" : "h-[170px] w-[146px]",
        config.stationClassName,
        agent.selected && "z-30",
      )}
      data-agent-role={agent.id}
      data-agent-frame={frame}
      aria-label={`查看 ${agent.name} 状态`}
      onClick={() => onSelectAgent?.(agent.id)}
    >
      {agent.active && (
        <span className="absolute inset-2 -z-10 rounded-xl bg-cyan-300/20 blur-xl group-hover:bg-cyan-300/30" />
      )}
      {!config.sprite && <PixelDesk config={config} director={director} />}
      <PixelCharacter config={config} frame={frame} director={director} />
      <SpeechBubble agent={agent} director={director} />
      <StatusCard agent={agent} director={director} />
      {agent.selected && (
        <span className="pointer-events-none absolute inset-0 rounded-lg ring-2 ring-cyan-200 ring-offset-2 ring-offset-[#101714]" />
      )}
    </button>
  );
}

function RoomHud({
  activeAgentCount,
  blockedAgentCount,
  selectedAgent,
}: {
  activeAgentCount: number;
  blockedAgentCount: number;
  selectedAgent?: LaunchCrewAgent;
}) {
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-40 flex items-start justify-between gap-3 p-2">
      <div className="min-w-0 rounded border border-cyan-200/30 bg-[#101714]/84 px-2 py-1 text-cyan-50 shadow-[2px_2px_0_rgba(5,10,9,0.6)] backdrop-blur-sm">
        <div className="text-[8px] font-black tracking-wide text-cyan-100/70 uppercase">
          Launch Crew War Room
        </div>
        <div className="max-w-[168px] truncate text-[10px] font-black">
          焦点：{selectedAgent?.shortName ?? "Launch Director"}
        </div>
      </div>
      <div className="flex shrink-0 gap-1.5 text-center">
        <div className="rounded border border-cyan-200/30 bg-[#101714]/84 px-2 py-1 text-cyan-50 shadow-[2px_2px_0_rgba(5,10,9,0.6)] backdrop-blur-sm">
          <div className="text-[11px] leading-none font-black">
            {activeAgentCount}/6
          </div>
          <div className="mt-0.5 text-[7px] font-bold text-cyan-100/70">
            ACTIVE
          </div>
        </div>
        <div className="rounded border border-cyan-200/30 bg-[#101714]/84 px-2 py-1 text-cyan-50 shadow-[2px_2px_0_rgba(5,10,9,0.6)] backdrop-blur-sm">
          <div className="text-[11px] leading-none font-black">
            {blockedAgentCount}
          </div>
          <div className="mt-0.5 text-[7px] font-bold text-cyan-100/70">
            BLOCK
          </div>
        </div>
      </div>
    </div>
  );
}

export function PixelOffice({
  agents,
  className,
  onSelectAgent,
}: PixelOfficeProps) {
  const activeAgentCount = agents.filter((agent) => agent.active).length;
  const selectedAgent = agents.find((agent) => agent.selected);
  const blockedAgentCount = agents.filter(
    (agent) => agent.status === "error",
  ).length;

  return (
    <section
      className={cn(
        "overflow-hidden rounded-lg border-2 border-[#17211d] bg-[#101714] shadow-[4px_4px_0_rgba(15,23,18,0.18)]",
        className,
      )}
      aria-label="EcomLaunch 多 agent 像素作战室"
    >
      <PixelRoom>
        <ConnectionLines active={activeAgentCount > 0} />
        {agents.map((agent) => (
          <AgentStation
            key={agent.id}
            agent={agent}
            onSelectAgent={onSelectAgent}
          />
        ))}
        <RoomHud
          activeAgentCount={activeAgentCount}
          blockedAgentCount={blockedAgentCount}
          selectedAgent={selectedAgent}
        />
      </PixelRoom>
    </section>
  );
}
