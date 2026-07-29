"use client";

import { cn } from "@/lib/utils";

type AgentRole =
  | "launch-director"
  | "market-voc-researcher"
  | "offer-architect"
  | "asset-studio"
  | "evidence-checker";

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
    name: string;
    position: string;
    color: string;
    animation: string;
  }
> = {
  "launch-director": {
    name: "EcomLaunch",
    position: "center",
    color: "bg-blue-500",
    animation: "animate-director",
  },
  "market-voc-researcher": {
    name: "市场研究员",
    position: "left-top",
    color: "bg-green-500",
    animation: "animate-researcher",
  },
  "offer-architect": {
    name: "方案架构师",
    position: "left-bottom",
    color: "bg-purple-500",
    animation: "animate-architect",
  },
  "asset-studio": {
    name: "素材工作室",
    position: "right-bottom",
    color: "bg-pink-500",
    animation: "animate-creator",
  },
  "evidence-checker": {
    name: "证据检查员",
    position: "center-bottom",
    color: "bg-red-500",
    animation: "animate-checker",
  },
};

const STATUS_CONFIG: Record<
  AgentStatus,
  {
    label: string;
    color: string;
    icon: string;
  }
> = {
  idle: { label: "空闲", color: "bg-gray-400", icon: "💤" },
  working: { label: "工作中", color: "bg-green-500", icon: "⚡" },
  thinking: { label: "思考中", color: "bg-yellow-500", icon: "💭" },
  done: { label: "已完成", color: "bg-blue-500", icon: "✅" },
  error: { label: "错误", color: "bg-red-500", icon: "❌" },
};

function PixelCharacter({
  role,
  status,
}: {
  role: AgentRole;
  status: AgentStatus;
}) {
  const agentConfig = AGENT_CONFIG[role];
  const statusConfig = STATUS_CONFIG[status];

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
        {statusConfig.label}
      </div>

      {/* 角色名称 */}
      <div className="text-muted-foreground mt-1 text-[10px]">
        {agentConfig.name}
      </div>
    </div>
  );
}

function WhiteBoard({
  progress,
  currentStage,
}: {
  progress: number;
  currentStage: string;
}) {
  return (
    <div className="rounded-lg border-2 border-amber-800 bg-white p-3 shadow-lg">
      {/* 白板标题 */}
      <div className="mb-2 flex justify-between text-[10px] font-bold">
        <span className="text-blue-600">TODO</span>
        <span className="text-yellow-600">IN PROC</span>
        <span className="text-green-600">DONE</span>
      </div>

      {/* 任务进度 */}
      <div className="space-y-1">
        {[
          "需求澄清",
          "市场与用户研究",
          "定位与验证",
          "内容资产",
          "证据审计",
        ].map((task, index) => {
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
        <div className="text-muted-foreground text-[10px]">当前阶段</div>
        <div className="text-xs font-medium">{currentStage || "等待中"}</div>
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
    "evidence-checker": "idle",
  },
  progress = 0,
  currentStage = "等待中",
}: PixelOfficeProps) {
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
          <WhiteBoard progress={progress} currentStage={currentStage} />
        </div>

        {/* 角色网格 */}
        <div className="grid grid-cols-3 gap-4">
          {/* 左侧 */}
          <div className="space-y-4">
            <PixelCharacter
              role="market-voc-researcher"
              status={agentStatuses["market-voc-researcher"]}
            />
            <PixelCharacter
              role="offer-architect"
              status={agentStatuses["offer-architect"]}
            />
          </div>

          {/* 中间 */}
          <div className="space-y-4">
            <PixelCharacter
              role="launch-director"
              status={agentStatuses["launch-director"]}
            />
            <PixelCharacter
              role="evidence-checker"
              status={agentStatuses["evidence-checker"]}
            />
          </div>

          {/* 右侧 */}
          <div className="space-y-4">
            <PixelCharacter
              role="asset-studio"
              status={agentStatuses["asset-studio"]}
            />
          </div>
        </div>

        {/* 状态栏 */}
        <div className="mt-4 rounded-lg border bg-white/80 p-3">
          <div className="flex items-center justify-between">
            <div className="text-muted-foreground text-xs">协作进度</div>
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
