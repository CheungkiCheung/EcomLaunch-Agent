"use client";

import { useI18n } from "@/core/i18n/hooks";
import type { Translations } from "@/core/i18n/locales/types";
import { cn } from "@/lib/utils";

type AgentRole =
  | "launch-director"
  | "market-voc-researcher"
  | "offer-architect"
  | "asset-studio";

type AgentStatus = "idle" | "working" | "thinking" | "done" | "error";

type PixelOfficeProps = {
  className?: string;
  agentStatuses?: Record<AgentRole, AgentStatus>;
  progress?: number;
  currentStage?: string;
};

const AGENT_CONFIG: Record<
  AgentRole,
  {
    position: string;
    color: string;
    animation: string;
  }
> = {
  "launch-director": {
    position: "center",
    color: "bg-blue-500",
    animation: "animate-director",
  },
  "market-voc-researcher": {
    position: "left-top",
    color: "bg-green-500",
    animation: "animate-researcher",
  },
  "offer-architect": {
    position: "left-bottom",
    color: "bg-purple-500",
    animation: "animate-architect",
  },
  "asset-studio": {
    position: "right-bottom",
    color: "bg-pink-500",
    animation: "animate-creator",
  },
};

const STATUS_CONFIG: Record<
  AgentStatus,
  {
    color: string;
    icon: string;
  }
> = {
  idle: { color: "bg-gray-400", icon: "💤" },
  working: { color: "bg-green-500", icon: "⚡" },
  thinking: { color: "bg-yellow-500", icon: "💭" },
  done: { color: "bg-blue-500", icon: "✅" },
  error: { color: "bg-red-500", icon: "❌" },
};

function PixelCharacter({
  role,
  status,
  copy,
  warRoomCopy,
}: {
  role: AgentRole;
  status: AgentStatus;
  copy: Translations["launchCrew"];
  warRoomCopy: Translations["warRoom"];
}) {
  const agentConfig = AGENT_CONFIG[role];
  const statusConfig = STATUS_CONFIG[status];
  const statusLabel =
    status === "thinking"
      ? copy.pixel.thinking
      : status === "error"
        ? copy.statuses.failed
        : status === "done"
          ? copy.statuses.done
          : status === "working"
            ? warRoomCopy.statuses.working
            : copy.statuses.idle;
  const agentName =
    role === "launch-director" ? copy.productName : copy.roles[role].name;

  return (
    <div className="relative flex flex-col items-center">
      {/* 角色像素艺术 */}
      <div
        className={cn(
          "relative h-12 w-12 rounded-lg transition-all duration-300",
          agentConfig.color,
          status === "working" && "animate-bounce",
          status === "thinking" && "animate-pulse",
        )}
      >
        {/* 像素角色简化表示 */}
        <div className="absolute inset-0 flex items-center justify-center text-lg text-white">
          {statusConfig.icon}
        </div>
      </div>

      {/* 状态标签 */}
      <div
        className={cn(
          "mt-1 rounded-full px-2 py-0.5 text-[10px] text-white",
          statusConfig.color,
        )}
      >
        {statusLabel}
      </div>

      {/* 角色名称 */}
      <div className="text-muted-foreground mt-1 text-[10px]">{agentName}</div>
    </div>
  );
}

function WhiteBoard({
  progress,
  currentStage,
  copy,
}: {
  progress: number;
  currentStage: string;
  copy: Translations["launchCrew"];
}) {
  return (
    <div className="w-full max-w-64 rounded-lg border-2 border-amber-800 bg-white p-3 shadow-lg">
      {/* 白板标题 */}
      <div className="mb-2 grid grid-cols-3 text-center text-[10px] font-bold">
        <span className="text-blue-600">{copy.pixel.todo}</span>
        <span className="text-yellow-600">{copy.pixel.inProgress}</span>
        <span className="text-green-600">{copy.pixel.done}</span>
      </div>

      {/* 任务进度 */}
      <div className="space-y-1">
        {copy.pixel.tasks.map((task, index) => {
          const taskProgress = Math.min(
            100,
            Math.max(0, progress - index * 15),
          );
          const status =
            taskProgress >= 100
              ? "done"
              : taskProgress > 0
                ? "working"
                : "idle";

          return (
            <div key={task} className="flex items-center gap-2">
              <div
                className={cn(
                  "h-2 w-2 rounded-full",
                  status === "done"
                    ? "bg-green-500"
                    : status === "working"
                      ? "bg-yellow-500"
                      : "bg-gray-300",
                )}
              />
              <span className="text-[10px] text-gray-600">{task}</span>
            </div>
          );
        })}
      </div>

      {/* 当前阶段 */}
      <div className="mt-2 border-t pt-2">
        <div className="text-muted-foreground text-[10px]">
          {copy.pixel.currentStage}
        </div>
        <div className="text-xs font-medium">
          {currentStage || copy.waiting}
        </div>
      </div>
    </div>
  );
}

export function PixelOffice({
  className,
  agentStatuses = {
    "launch-director": "idle",
    "market-voc-researcher": "idle",
    "offer-architect": "idle",
    "asset-studio": "idle",
  },
  progress = 0,
  currentStage,
}: PixelOfficeProps) {
  const { t } = useI18n();
  const copy = t.launchCrew;
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border bg-gradient-to-br from-amber-50 to-orange-50",
        className,
      )}
    >
      {/* 办公室背景 */}
      <div className="absolute inset-0 opacity-20">
        <div className="h-full w-full bg-[url('/pixel-office-bg.png')] bg-cover bg-center" />
      </div>

      {/* 内容区域 */}
      <div className="relative z-10 p-4">
        {/* 白板 */}
        <div className="mb-4 flex justify-center">
          <WhiteBoard
            progress={progress}
            currentStage={currentStage ?? copy.waiting}
            copy={copy}
          />
        </div>

        {/* 角色网格 */}
        <div className="grid grid-cols-3 gap-4">
          {/* 左侧 */}
          <div className="space-y-4">
            <PixelCharacter
              role="market-voc-researcher"
              status={agentStatuses["market-voc-researcher"]}
              copy={copy}
              warRoomCopy={t.warRoom}
            />
            <PixelCharacter
              role="offer-architect"
              status={agentStatuses["offer-architect"]}
              copy={copy}
              warRoomCopy={t.warRoom}
            />
          </div>

          {/* 中间 */}
          <div className="space-y-4">
            <PixelCharacter
              role="launch-director"
              status={agentStatuses["launch-director"]}
              copy={copy}
              warRoomCopy={t.warRoom}
            />
          </div>

          {/* 右侧 */}
          <div className="space-y-4">
            <PixelCharacter
              role="asset-studio"
              status={agentStatuses["asset-studio"]}
              copy={copy}
              warRoomCopy={t.warRoom}
            />
          </div>
        </div>

        {/* 状态栏 */}
        <div className="mt-4 rounded-lg border bg-white/80 p-3">
          <div className="flex items-center justify-between">
            <div className="text-muted-foreground text-xs">
              {copy.collaborationProgress}
            </div>
            <div className="text-xs font-medium">{progress}%</div>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full bg-gradient-to-r from-green-400 to-blue-500 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
