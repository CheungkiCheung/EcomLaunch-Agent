"use client";

import type { Message } from "@langchain/langgraph-sdk";
import {
  AlertCircleIcon,
  CheckCircle2Icon,
  CircleDotDashedIcon,
  FileTextIcon,
  Loader2Icon,
  MessageSquareTextIcon,
  PackageCheckIcon,
  ShieldCheckIcon,
  TargetIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { useArtifacts } from "@/components/workspace/artifacts";
import { useI18n } from "@/core/i18n/hooks";
import { useSubtaskContext } from "@/core/tasks/context";
import type { AgentThreadState } from "@/core/threads";
import { explainLastToolCall } from "@/core/tools/utils";
import { cn } from "@/lib/utils";

import {
  type LaunchCrewActivityModel,
  type LaunchCrewAgent,
  type LaunchCrewArtifact,
  type LaunchCrewCommsEvent,
  type LaunchCrewEvidenceBadge,
  type LaunchCrewMission,
  type LaunchCrewRole,
} from "./launch-crew-activity-model";
import { PixelOffice } from "./pixel-office";
import { buildLaunchCrewActivityModelFromThread } from "./use-launch-crew-activity-model";

type LaunchCrewPanelProps = {
  className?: string;
  threadValues: AgentThreadState;
  messages: Message[];
  isStreaming: boolean;
};

function statusIcon(agent: LaunchCrewAgent) {
  if (agent.status === "error") {
    return <AlertCircleIcon className="size-3.5" />;
  }
  if (agent.status === "done" || agent.status === "delivered") {
    return <CheckCircle2Icon className="size-3.5" />;
  }
  if (agent.status !== "idle") {
    return <Loader2Icon className="size-3.5 animate-spin" />;
  }
  return <CircleDotDashedIcon className="size-3.5" />;
}

function statusLabel(agent: LaunchCrewAgent) {
  switch (agent.status) {
    case "searching":
      return "搜索中";
    case "reading":
      return "阅读中";
    case "writing":
      return "写作中";
    case "working":
      return "行动中";
    case "done":
    case "delivered":
      return "已回传";
    case "error":
      return "阻塞";
    default:
      return "待命";
  }
}

function evidenceBadgeVariant(status: LaunchCrewEvidenceBadge["status"]) {
  if (status === "ready") {
    return "secondary" as const;
  }
  if (status === "active") {
    return "default" as const;
  }
  return "outline" as const;
}

function EvidenceBadges({ badges }: { badges: LaunchCrewEvidenceBadge[] }) {
  return (
    <section className="grid grid-cols-2 gap-2">
      {badges.map((badge) => (
        <Badge
          key={badge.id}
          variant={evidenceBadgeVariant(badge.status)}
          className="h-8 min-w-0 justify-start gap-1.5 px-2 text-[11px]"
        >
          <ShieldCheckIcon className="size-3 shrink-0" />
          <span className="truncate">{badge.label}</span>
        </Badge>
      ))}
    </section>
  );
}

function SelectedAgentDetail({
  agent,
  onOpenArtifact,
}: {
  agent: LaunchCrewAgent;
  onOpenArtifact: (filepath: string) => void;
}) {
  return (
    <section className="border-border/80 bg-card rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-muted-foreground text-[11px] font-medium">
            Selected Agent
          </div>
          <h3 className="truncate text-sm font-semibold">{agent.name}</h3>
          <p className="text-muted-foreground mt-0.5 truncate text-xs">
            {agent.desk}
          </p>
        </div>
        <Badge
          variant={
            agent.status === "error"
              ? "destructive"
              : agent.status === "done" || agent.status === "delivered"
                ? "secondary"
                : "outline"
          }
          className="shrink-0 gap-1"
        >
          {statusIcon(agent)}
          {statusLabel(agent)}
        </Badge>
      </div>

      <div className="bg-muted/40 mt-3 rounded-md px-3 py-2 text-xs leading-5">
        {agent.lastLine}
      </div>

      {agent.task && (
        <div className="mt-3 space-y-2">
          <div>
            <div className="text-muted-foreground mb-1 text-[10px] font-medium tracking-wide uppercase">
              分派任务
            </div>
            <p className="text-xs leading-5 break-words">
              {agent.task.description}
            </p>
          </div>
          {agent.currentAction && (
            <div>
              <div className="text-muted-foreground mb-1 text-[10px] font-medium tracking-wide uppercase">
                当前动作
              </div>
              <p className="text-xs leading-5 break-words">
                {agent.currentAction}
              </p>
            </div>
          )}
        </div>
      )}

      {agent.artifacts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {agent.artifacts.map((artifact) => (
            <Button
              key={artifact.filepath}
              type="button"
              variant="outline"
              size="sm"
              className="h-7 max-w-full min-w-0 px-2 text-xs"
              onClick={() => onOpenArtifact(artifact.filepath)}
            >
              <PackageCheckIcon className="size-3.5" />
              <span className="truncate">{artifact.name}</span>
            </Button>
          ))}
        </div>
      )}
    </section>
  );
}

function LiveComms({ events }: { events: LaunchCrewCommsEvent[] }) {
  return (
    <section>
      <div className="text-muted-foreground mb-2 inline-flex items-center gap-1 text-xs font-medium">
        <MessageSquareTextIcon className="size-3.5" />
        Live Comms
      </div>
      {events.length === 0 ? (
        <div className="border-border/80 bg-muted/20 text-muted-foreground rounded-lg border p-3 text-xs">
          等待第一条 agent 状态回传。
        </div>
      ) : (
        <div className="space-y-2">
          {events.map((event) => (
            <div
              key={event.id}
              className="border-border/80 bg-background rounded-md border px-3 py-2"
            >
              <div className="text-[11px] font-medium">{event.speaker}</div>
              <div className="text-muted-foreground mt-0.5 line-clamp-2 text-xs leading-5">
                {event.text}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ActiveMissions({ missions }: { missions: LaunchCrewMission[] }) {
  return (
    <section>
      <div className="text-muted-foreground mb-2 inline-flex items-center gap-1 text-xs font-medium">
        <TargetIcon className="size-3.5" />
        Active Missions
      </div>
      {missions.length === 0 ? (
        <div className="border-border/80 bg-muted/20 text-muted-foreground rounded-lg border p-3 text-xs">
          暂无活动任务。发送上新验证请求后，这里会显示当前焦点。
        </div>
      ) : (
        <div className="space-y-2">
          {missions.map((mission) => (
            <div
              key={mission.id}
              className="border-border/80 bg-background flex items-center justify-between gap-3 rounded-md border px-3 py-2"
            >
              <span className="min-w-0 truncate text-xs">{mission.label}</span>
              <Badge
                variant={mission.status === "done" ? "secondary" : "outline"}
                className="shrink-0 text-[10px]"
              >
                {mission.status === "done"
                  ? "done"
                  : mission.status === "active"
                    ? "live"
                    : "next"}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ArtifactConveyor({
  artifacts,
  onOpenArtifact,
}: {
  artifacts: LaunchCrewArtifact[];
  onOpenArtifact: (filepath: string) => void;
}) {
  return (
    <section>
      <div className="text-muted-foreground mb-2 inline-flex items-center gap-1 text-xs font-medium">
        <FileTextIcon className="size-3.5" />
        Artifact Conveyor
      </div>
      <div className="space-y-2">
        {artifacts.map((artifact) => {
          const ready = artifact.status === "ready";
          return (
            <button
              key={`${artifact.filepath}-${artifact.status}`}
              type="button"
              disabled={!ready}
              className={cn(
                "border-border/80 flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors",
                ready
                  ? "bg-background hover:bg-accent/60"
                  : "bg-muted/20 text-muted-foreground",
              )}
              onClick={() => ready && onOpenArtifact(artifact.filepath)}
            >
              {ready ? (
                <PackageCheckIcon className="text-primary size-4 shrink-0" />
              ) : (
                <CircleDotDashedIcon className="size-4 shrink-0" />
              )}
              <span className="min-w-0 flex-1 truncate">{artifact.label}</span>
              <Badge
                variant={ready ? "secondary" : "outline"}
                className="shrink-0 text-[10px]"
              >
                {ready ? "ready" : "pending"}
              </Badge>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function buildActivityModel({
  messages,
  contextTasks,
  threadValues,
  selectedAgentId,
  isStreaming,
  explainAction,
}: {
  messages: Message[];
  contextTasks: Parameters<
    typeof buildLaunchCrewActivityModelFromThread
  >[0]["contextTasks"];
  threadValues: AgentThreadState;
  selectedAgentId: LaunchCrewRole | null;
  isStreaming: boolean;
  explainAction: Parameters<
    typeof buildLaunchCrewActivityModelFromThread
  >[0]["explainAction"];
}): LaunchCrewActivityModel {
  return buildLaunchCrewActivityModelFromThread({
    messages,
    contextTasks,
    threadValues,
    selectedAgentId,
    isStreaming,
    explainAction,
  });
}

export function LaunchCrewPanel({
  className,
  threadValues,
  messages,
  isStreaming,
}: LaunchCrewPanelProps) {
  const { t } = useI18n();
  const { tasks } = useSubtaskContext();
  const { select: selectArtifact, setOpen: setArtifactsOpen } = useArtifacts();
  const [selectedAgentId, setSelectedAgentId] = useState<LaunchCrewRole | null>(
    null,
  );

  const model = useMemo(
    () =>
      buildActivityModel({
        messages,
        contextTasks: tasks,
        threadValues,
        selectedAgentId,
        isStreaming,
        explainAction: (task) =>
          task.latestMessage
            ? explainLastToolCall(task.latestMessage, t)
            : null,
      }),
    [isStreaming, messages, selectedAgentId, t, tasks, threadValues],
  );

  const openArtifact = (filepath: string) => {
    selectArtifact(filepath);
    setArtifactsOpen(true);
  };

  return (
    <aside
      aria-label="EcomLaunch live agent cockpit"
      className={cn(
        "border-border/80 bg-background/80 hidden h-full min-h-0 w-[460px] shrink-0 border-l backdrop-blur xl:flex 2xl:w-[520px]",
        className,
      )}
    >
      <div className="flex min-h-0 w-full flex-col">
        <header className="shrink-0 px-4 pt-4 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-muted-foreground text-xs font-medium">
                EcomLaunch
              </div>
              <h2 className="text-base leading-tight font-semibold">
                Live Agent Cockpit
              </h2>
            </div>
            <Badge variant={isStreaming ? "default" : "secondary"}>
              {isStreaming ? "协作中" : "已同步"}
            </Badge>
          </div>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">协作进度</span>
              <span className="font-medium">
                {model.completedAgentCount}/
                {Math.max(model.activeAgentCount, 1)}
              </span>
            </div>
            <Progress className="h-1.5" value={model.progress} />
          </div>
        </header>

        <Separator />

        <div className="shrink-0 px-4 py-3">
          <PixelOffice
            agents={model.agents}
            onSelectAgent={setSelectedAgentId}
          />
        </div>

        <Separator />

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <EvidenceBadges badges={model.evidenceBadges} />
          <SelectedAgentDetail
            agent={model.selectedAgent}
            onOpenArtifact={openArtifact}
          />
          <LiveComms events={model.liveComms} />
          <ActiveMissions missions={model.activeMissions} />
          <ArtifactConveyor
            artifacts={model.artifactStatuses}
            onOpenArtifact={openArtifact}
          />
        </div>
      </div>
    </aside>
  );
}
