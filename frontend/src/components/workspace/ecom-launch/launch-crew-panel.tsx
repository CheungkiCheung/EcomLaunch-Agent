"use client";

import type { Message } from "@langchain/langgraph-sdk";
import {
  CheckCircle2Icon,
  CircleDotDashedIcon,
  FileTextIcon,
  Loader2Icon,
  PackageCheckIcon,
  SearchIcon,
  SparklesIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { useArtifacts } from "@/components/workspace/artifacts";
import { isCompleteLaunchPack } from "@/core/artifacts/launch-pack";
import { useI18n } from "@/core/i18n/hooks";
import type { Translations } from "@/core/i18n/locales/types";
import {
  extractPresentedFilesFromMessages,
  extractTextFromMessage,
} from "@/core/messages/utils";
import { useSubtaskContext } from "@/core/tasks/context";
import { parseSubtaskResult } from "@/core/tasks/subtask-result";
import type { Subtask } from "@/core/tasks/types";
import type { AgentThreadState } from "@/core/threads";
import type { Todo } from "@/core/todos";
import { explainLastToolCall } from "@/core/tools/utils";
import { getFileName } from "@/core/utils/files";
import { cn } from "@/lib/utils";

import { PixelOffice } from "./pixel-office";

type LaunchCrewRole =
  | "market-voc-researcher"
  | "offer-architect"
  | "asset-studio";

type LaunchCrewStatus =
  | "idle"
  | "assigned"
  | "searching"
  | "reading"
  | "writing"
  | "delivered"
  | "done"
  | "failed";

type LaunchCrewRoleConfig = {
  id: LaunchCrewRole;
  accent: string;
  icon: React.ComponentType<{ className?: string }>;
};

type RequiredDeliverable = {
  filepath: string;
  label: string;
};

type WorkflowStage = {
  id: string;
  label: string;
  matchers: string[];
  artifactNames?: string[];
};

type LaunchCrewPanelProps = {
  className?: string;
  threadValues: AgentThreadState;
  messages: Message[];
  isStreaming: boolean;
};

const ROLE_CONFIGS: LaunchCrewRoleConfig[] = [
  {
    id: "market-voc-researcher",
    accent: "bg-cyan-500",
    icon: SearchIcon,
  },
  {
    id: "offer-architect",
    accent: "bg-emerald-500",
    icon: SparklesIcon,
  },
  {
    id: "asset-studio",
    accent: "bg-fuchsia-500",
    icon: FileTextIcon,
  },
];

const ARTIFACT_TO_ROLE: Array<[string, LaunchCrewRole]> = [
  ["competitor-table.csv", "market-voc-researcher"],
  ["source-list.md", "market-voc-researcher"],
  ["review-insights.json", "market-voc-researcher"],
  ["positioning-brief.md", "offer-architect"],
  ["launch-calendar.csv", "offer-architect"],
  ["listing-pack.md", "asset-studio"],
  ["content-pack.md", "asset-studio"],
];

function getRequiredDeliverables(
  copy: Translations["launchCrew"],
): RequiredDeliverable[] {
  return [
    {
      filepath: "competitor-table.csv",
      label: copy.deliverableLabels.competitorTable,
    },
    {
      filepath: "evidence-ledger.json",
      label: copy.deliverableLabels.evidenceLedger,
    },
    {
      filepath: "positioning-brief.md",
      label: copy.deliverableLabels.positioningBrief,
    },
    {
      filepath: "listing-pack.md",
      label: copy.deliverableLabels.listingPack,
    },
    {
      filepath: "content-pack.md",
      label: copy.deliverableLabels.contentPack,
    },
    {
      filepath: "launch-calendar.csv",
      label: copy.deliverableLabels.launchCalendar,
    },
    {
      filepath: "launch-war-room.html",
      label: copy.deliverableLabels.warRoomPage,
    },
  ];
}

const WORKFLOW_STAGES: WorkflowStage[] = [
  {
    id: "brief",
    label: "Brief",
    matchers: ["clarify", "brief", "context", "launch brief", "启动", "简报"],
    artifactNames: ["positioning-brief.md"],
  },
  {
    id: "research",
    label: "Research",
    matchers: [
      "market",
      "voc",
      "research",
      "signal",
      "customer",
      "review",
      "市场",
      "用户",
      "研究",
    ],
    artifactNames: ["competitor-table.csv", "review-insights.json"],
  },
  {
    id: "offer",
    label: "Offer",
    matchers: ["offer", "position", "wedge", "hypoth", "定位", "卖点", "假设"],
    artifactNames: ["positioning-brief.md"],
  },
  {
    id: "assets",
    label: "Assets",
    matchers: ["asset", "listing", "content", "copy", "素材", "内容", "文案"],
    artifactNames: ["listing-pack.md", "content-pack.md"],
  },
  {
    id: "plan",
    label: "Plan",
    matchers: [
      "7-day",
      "validation plan",
      "calendar",
      "experiment",
      "验证计划",
      "7 天",
    ],
    artifactNames: ["launch-calendar.csv"],
  },
  {
    id: "audit",
    label: "Evidence",
    matchers: [
      "audit",
      "evidence",
      "claim",
      "unsupported",
      "证据",
      "口径",
      "审计",
    ],
    artifactNames: ["evidence-ledger.json"],
  },
  {
    id: "pack",
    label: "Delivery",
    matchers: ["present", "artifact", "deliver", "输出", "交付"],
    artifactNames: ["launch-war-room.html"],
  },
];

function localizedWorkflowStages(
  copy: Translations["launchCrew"],
): WorkflowStage[] {
  return WORKFLOW_STAGES.map((stage) => ({
    ...stage,
    label:
      copy.workflowStages[
        stage.id as keyof Translations["launchCrew"]["workflowStages"]
      ],
  }));
}

function roleForArtifact(filepath: string): LaunchCrewRole | "launch-director" {
  const name = getFileName(filepath);
  const match = ARTIFACT_TO_ROLE.find(
    ([artifactName]) => name === artifactName,
  );
  return match?.[1] ?? "launch-director";
}

function normalizeRole(role: string | undefined): LaunchCrewRole | null {
  if (!role) {
    return null;
  }
  return ROLE_CONFIGS.some((config) => config.id === role)
    ? (role as LaunchCrewRole)
    : null;
}

function latestTaskForRole(tasks: Subtask[], role: LaunchCrewRole) {
  return [...tasks].reverse().find((task) => task.subagent_type === role);
}

function fallbackTasksFromMessages(messages: Message[]) {
  const taskMap = new Map<string, Subtask>();

  for (const message of messages) {
    if (message.type === "ai") {
      for (const toolCall of message.tool_calls ?? []) {
        if (toolCall.name !== "task" || !toolCall.id) {
          continue;
        }
        const args = toolCall.args as {
          subagent_type?: string;
          description?: string;
          prompt?: string;
        };
        const role = normalizeRole(args.subagent_type);
        if (!role) {
          continue;
        }
        taskMap.set(toolCall.id, {
          id: toolCall.id,
          subagent_type: role,
          description: args.description ?? role,
          prompt: args.prompt ?? "",
          status: "in_progress",
          latestMessage: message,
        });
      }
      continue;
    }

    if (message.type === "tool" && typeof message.tool_call_id === "string") {
      const task = taskMap.get(message.tool_call_id);
      if (!task) {
        continue;
      }
      taskMap.set(message.tool_call_id, {
        ...task,
        ...parseSubtaskResult(
          extractTextFromMessage(message),
          message.additional_kwargs,
        ),
      });
    }
  }

  return [...taskMap.values()];
}

function fallbackArtifactsFromMessages(messages: Message[]) {
  return extractPresentedFilesFromMessages(messages);
}

function getToolName(task: Subtask | undefined) {
  return task?.latestMessage?.tool_calls?.at(-1)?.name;
}

function isWorkingStatus(status: LaunchCrewStatus) {
  return (
    status === "assigned" ||
    status === "searching" ||
    status === "reading" ||
    status === "writing"
  );
}

function getPhaseLabels(
  status: LaunchCrewStatus,
  copy: Translations["launchCrew"],
) {
  return [
    {
      label: copy.phases.assign,
      active: status !== "idle",
      done: status !== "idle",
    },
    {
      label: copy.phases.collect,
      active: status === "searching" || status === "reading",
      done:
        status === "writing" ||
        status === "done" ||
        status === "delivered" ||
        status === "failed",
    },
    {
      label: copy.phases.organize,
      active: status === "writing",
      done: status === "done" || status === "delivered",
    },
    {
      label: copy.phases.return,
      active: status === "done" || status === "delivered",
      done: status === "done" || status === "delivered",
    },
  ];
}

function getTodoStageStatus(
  todos: Todo[] | undefined,
  stage: WorkflowStage,
): Todo["status"] | undefined {
  const todo = todos?.find((item) => {
    const content = item.content?.toLowerCase() ?? "";
    return stage.matchers.some((matcher) =>
      content.includes(matcher.toLowerCase()),
    );
  });
  return todo?.status;
}

function statusForTask(
  task: Subtask | undefined,
  artifacts: string[],
): LaunchCrewStatus {
  if (!task) {
    return "idle";
  }
  if (task.status === "failed") {
    return "failed";
  }
  if (task.status === "completed") {
    return "done";
  }

  const toolName = getToolName(task);
  if (toolName === "web_search" || toolName === "image_search") {
    return "searching";
  }
  if (toolName === "web_fetch" || toolName === "read_file") {
    return "reading";
  }
  if (toolName === "write_file" || toolName === "present_files") {
    return "writing";
  }

  return artifacts.length > 0 ? "writing" : "assigned";
}

function statusLabel(
  status: LaunchCrewStatus,
  copy: Translations["launchCrew"],
) {
  return copy.statuses[status];
}

function bubbleForTask(
  task: Subtask | undefined,
  status: LaunchCrewStatus,
  artifactCount: number,
  copy: Translations["launchCrew"],
) {
  if (!task) {
    if (status === "delivered" && artifactCount > 0) {
      return copy.bubbles.delivered;
    }
    return copy.bubbles.waiting;
  }
  if (status === "failed") {
    return task.error ?? copy.bubbles.blocked;
  }
  if (status === "done") {
    return task.result
      ? copy.bubbles.resultReturned
      : copy.bubbles.taskCompleted;
  }

  const toolName = getToolName(task);
  if (toolName === "web_search" || toolName === "image_search") {
    return copy.bubbles.searching;
  }
  if (toolName === "web_fetch") {
    return copy.bubbles.fetching;
  }
  if (toolName === "read_file") {
    return copy.bubbles.reading;
  }
  return task.description || copy.bubbles.working;
}

function statusIcon(status: LaunchCrewStatus) {
  if (status === "done" || status === "delivered") {
    return <CheckCircle2Icon className="size-3.5" />;
  }
  if (status === "failed") {
    return <TriangleAlertIcon className="size-3.5" />;
  }
  if (status !== "idle") {
    return <Loader2Icon className="size-3.5 animate-spin" />;
  }
  return <CircleDotDashedIcon className="size-3.5" />;
}

export function LaunchCrewPanel({
  className,
  threadValues,
  messages,
  isStreaming,
}: LaunchCrewPanelProps) {
  const { t } = useI18n();
  const copy = t.launchCrew;
  const { tasks } = useSubtaskContext();
  const { select: selectArtifact, setOpen: setArtifactsOpen } = useArtifacts();
  const fallbackTasks = useMemo(
    () => fallbackTasksFromMessages(messages),
    [messages],
  );
  const taskList = useMemo(() => {
    const taskMap = new Map<string, Subtask>();
    for (const task of fallbackTasks) {
      taskMap.set(task.id, task);
    }
    for (const task of Object.values(tasks)) {
      taskMap.set(task.id, task);
    }
    return [...taskMap.values()];
  }, [fallbackTasks, tasks]);
  const fallbackArtifacts = useMemo(
    () => fallbackArtifactsFromMessages(messages),
    [messages],
  );
  const artifacts = useMemo(
    () => [
      ...new Set([...(threadValues.artifacts ?? []), ...fallbackArtifacts]),
    ],
    [fallbackArtifacts, threadValues.artifacts],
  );
  const mappedArtifacts = useMemo(
    () =>
      artifacts.map((filepath) => ({
        filepath,
        name: getFileName(filepath),
        role: roleForArtifact(filepath),
      })),
    [artifacts],
  );
  const requiredDeliverables = useMemo(() => {
    const artifactByName = new Map(
      mappedArtifacts.map((artifact) => [artifact.name, artifact]),
    );
    return getRequiredDeliverables(copy).map((deliverable) => {
      const artifact = artifactByName.get(deliverable.filepath);
      return {
        ...deliverable,
        artifact,
        complete: Boolean(artifact),
      };
    });
  }, [copy, mappedArtifacts]);
  const completedDeliverableCount = requiredDeliverables.filter(
    (deliverable) => deliverable.complete,
  ).length;
  const missingDeliverables = requiredDeliverables.filter(
    (deliverable) => !deliverable.complete,
  );
  const workflowStages = useMemo(() => {
    const artifactNames = new Set(
      mappedArtifacts.map((artifact) => artifact.name),
    );
    return localizedWorkflowStages(copy).map((stage) => {
      const todoStatus = getTodoStageStatus(threadValues.todos, stage);
      const artifactComplete =
        stage.artifactNames?.some((name) => artifactNames.has(name)) ?? false;
      const status =
        todoStatus === "completed" || artifactComplete
          ? "completed"
          : todoStatus === "in_progress"
            ? "in_progress"
            : "pending";
      return { ...stage, status };
    });
  }, [copy, mappedArtifacts, threadValues.todos]);
  const currentStage =
    workflowStages.find((stage) => stage.status === "in_progress") ??
    workflowStages.find((stage) => stage.status === "pending");

  const activeRoles = useMemo(() => {
    const roles = new Set<LaunchCrewRole>();
    for (const task of taskList) {
      const role = normalizeRole(task.subagent_type);
      if (role) {
        roles.add(role);
      }
    }
    return roles;
  }, [taskList]);

  const roleViews = ROLE_CONFIGS.map((config) => {
    const task = latestTaskForRole(taskList, config.id);
    const roleArtifacts = mappedArtifacts.filter(
      (artifact) => artifact.role === config.id,
    );
    const status = !task
      ? "idle"
      : roleArtifacts.length > 0 && task.status === "completed"
        ? "done"
        : statusForTask(
            task,
            roleArtifacts.map((artifact) => artifact.filepath),
          );
    return {
      ...config,
      ...copy.roles[config.id],
      task,
      artifacts: roleArtifacts,
      status,
      currentAction:
        task?.latestMessage && task.status === "in_progress"
          ? explainLastToolCall(task.latestMessage, t)
          : null,
      // Flash uses the deterministic renderer without specialist task events.
      // Do not make an artifact's ownership look like a specialist actually ran.
      visible: activeRoles.has(config.id) || (isStreaming && Boolean(task)),
    };
  });

  const visibleRoles = roleViews.filter((role) => role.visible);
  const completedCount = roleViews.filter(
    (role) => role.status === "done" || role.status === "delivered",
  ).length;
  const assignedCount = roleViews.filter(
    (role) => role.status !== "idle",
  ).length;
  const deliverableProgress =
    requiredDeliverables.length === 0
      ? 0
      : Math.round(
          (completedDeliverableCount / requiredDeliverables.length) * 100,
        );
  const hasCompletePack = isCompleteLaunchPack(artifacts);
  const progress =
    assignedCount > 0
      ? Math.round((completedCount / Math.max(assignedCount, 1)) * 100)
      : deliverableProgress;
  const progressLabel =
    assignedCount > 0 ? copy.collaborationProgress : copy.deliveryProgress;
  const progressCount =
    assignedCount > 0
      ? `${completedCount}/${Math.max(assignedCount, 1)}`
      : `${completedDeliverableCount}/${requiredDeliverables.length}`;

  const openArtifact = (filepath: string) => {
    selectArtifact(filepath);
    setArtifactsOpen(true);
  };

  return (
    <aside
      className={cn(
        "border-border/80 bg-background/80 hidden h-full min-h-0 w-[380px] shrink-0 border-l pt-12 backdrop-blur xl:flex",
        className,
      )}
    >
      <div className="flex min-h-0 w-full flex-col">
        <header className="shrink-0 px-4 pt-4 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-muted-foreground text-xs font-medium">
                {copy.productName}
              </div>
              <h2 className="text-base leading-tight font-semibold">
                {copy.title}
              </h2>
            </div>
            <Badge variant={isStreaming ? "default" : "secondary"}>
              {isStreaming ? copy.collaborating : copy.synced}
            </Badge>
          </div>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{progressLabel}</span>
              <span className="font-medium">{progressCount}</span>
            </div>
            <Progress className="h-1.5" value={progress} />
          </div>
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between gap-2 text-xs">
              <span className="text-muted-foreground">
                {copy.validationStage}
              </span>
              <span className="max-w-32 truncate font-medium">
                {currentStage ? currentStage.label : copy.complete}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {workflowStages.map((stage) => (
                <div
                  key={stage.id}
                  className={cn(
                    "rounded-sm border px-1 py-1 text-center text-[10px] leading-none",
                    stage.status === "completed"
                      ? "border-primary/20 bg-primary/10 text-primary"
                      : stage.status === "in_progress"
                        ? "border-border bg-muted text-foreground"
                        : "border-border/60 text-muted-foreground",
                  )}
                >
                  {stage.label}
                </div>
              ))}
            </div>
          </div>
        </header>

        <Separator />

        {/* 像素艺术办公室 */}
        <div className="shrink-0 px-4 py-3">
          <PixelOffice
            agentStatuses={{
              "launch-director": isStreaming
                ? "working"
                : hasCompletePack
                  ? "done"
                  : "idle",
              "market-voc-researcher": visibleRoles.some(
                (r) =>
                  r.id === "market-voc-researcher" && isWorkingStatus(r.status),
              )
                ? "working"
                : visibleRoles.some(
                      (r) =>
                        r.id === "market-voc-researcher" &&
                        (r.status === "done" || r.status === "delivered"),
                    )
                  ? "done"
                  : "idle",
              "offer-architect": visibleRoles.some(
                (r) => r.id === "offer-architect" && isWorkingStatus(r.status),
              )
                ? "working"
                : visibleRoles.some(
                      (r) =>
                        r.id === "offer-architect" &&
                        (r.status === "done" || r.status === "delivered"),
                    )
                  ? "done"
                  : "idle",
              "asset-studio": visibleRoles.some(
                (r) => r.id === "asset-studio" && isWorkingStatus(r.status),
              )
                ? "working"
                : visibleRoles.some(
                      (r) =>
                        r.id === "asset-studio" &&
                        (r.status === "done" || r.status === "delivered"),
                    )
                  ? "done"
                  : "idle",
            }}
            progress={progress}
            progressLabel={progressLabel}
            currentStage={
              currentStage?.label ??
              (hasCompletePack ? copy.complete : copy.waiting)
            }
          />
        </div>

        <Separator />

        {(visibleRoles.length > 0 ||
          mappedArtifacts.length > 0 ||
          isStreaming) && (
          <section className="border-border/80 bg-muted/10 shrink-0 border-b px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-muted-foreground text-xs font-medium">
                  {copy.deliveryChecklist}
                </div>
                <div className="text-muted-foreground/80 text-[11px]">
                  {copy.coreFilesComplete(
                    completedDeliverableCount,
                    requiredDeliverables.length,
                  )}
                </div>
              </div>
              <Badge
                variant={deliverableProgress === 100 ? "secondary" : "outline"}
              >
                {deliverableProgress === 100 ? copy.allPresent : copy.advancing}
              </Badge>
            </div>
            <Progress className="mt-2 h-1.5" value={deliverableProgress} />

            {missingDeliverables.length > 0 && (
              <div className="mt-3 space-y-2">
                <div className="text-muted-foreground text-[11px] font-medium">
                  {copy.missing}
                </div>
                <div className="space-y-2">
                  {missingDeliverables.map((deliverable) => (
                    <div
                      key={deliverable.filepath}
                      className="border-border/80 bg-background flex items-center justify-between gap-3 rounded-md border px-3 py-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-xs font-medium">
                          {deliverable.label}
                        </div>
                        <div className="text-muted-foreground truncate text-[11px]">
                          {deliverable.filepath}
                        </div>
                      </div>
                      <Badge variant="outline" className="shrink-0 gap-1">
                        <CircleDotDashedIcon className="size-3" />
                        {copy.pendingGeneration}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <section className="space-y-3">
            {visibleRoles.length === 0 ? (
              <div className="border-border/80 bg-muted/20 rounded-lg border p-4 text-sm">
                <div className="font-medium">
                  {hasCompletePack ? copy.packCompleteTitle : copy.emptyTitle}
                </div>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  {hasCompletePack
                    ? copy.packCompleteDescription
                    : copy.emptyDescription}
                </p>
              </div>
            ) : (
              visibleRoles.map((role) => {
                const Icon = role.icon;
                return (
                  <article
                    key={role.id}
                    className="border-border/80 bg-card rounded-lg border p-3"
                  >
                    <div className="flex items-start gap-3">
                      <div className="relative shrink-0">
                        <div className="bg-muted flex size-9 items-center justify-center rounded-md">
                          <Icon className="size-4" />
                        </div>
                        <span
                          className={cn(
                            "ring-background absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2",
                            role.accent,
                            isWorkingStatus(role.status) && "animate-pulse",
                          )}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <h3 className="truncate text-sm font-medium">
                              {role.name}
                            </h3>
                            <p className="text-muted-foreground text-xs">
                              {role.desk}
                            </p>
                          </div>
                          <Badge
                            variant={
                              role.status === "failed"
                                ? "destructive"
                                : role.status === "done" ||
                                    role.status === "delivered"
                                  ? "secondary"
                                  : "outline"
                            }
                            className="gap-1"
                          >
                            {statusIcon(role.status)}
                            {statusLabel(role.status, copy)}
                          </Badge>
                        </div>

                        <div className="bg-muted/40 mt-3 rounded-md px-3 py-2 text-xs leading-5">
                          {bubbleForTask(
                            role.task,
                            role.status,
                            role.artifacts.length,
                            copy,
                          )}
                        </div>

                        {(role.task ?? role.currentAction) && (
                          <div className="mt-3 space-y-2">
                            {role.task && (
                              <div>
                                <div className="text-muted-foreground mb-1 text-[10px] font-medium tracking-wide uppercase">
                                  {copy.assignedTask}
                                </div>
                                <p className="text-xs leading-5 break-words">
                                  {role.task.description}
                                </p>
                              </div>
                            )}
                            {role.currentAction && (
                              <div>
                                <div className="text-muted-foreground mb-1 text-[10px] font-medium tracking-wide uppercase">
                                  {copy.currentAction}
                                </div>
                                <p className="text-xs leading-5 break-words">
                                  {role.currentAction}
                                </p>
                              </div>
                            )}
                          </div>
                        )}

                        {role.task && role.status !== "idle" && (
                          <div className="mt-3 grid grid-cols-4 gap-1">
                            {getPhaseLabels(role.status, copy).map((phase) => (
                              <div
                                key={phase.label}
                                className={cn(
                                  "rounded-sm border px-1.5 py-1 text-center text-[10px] leading-none",
                                  phase.done
                                    ? "border-primary/20 bg-primary/10 text-primary"
                                    : phase.active
                                      ? "border-border bg-muted text-foreground"
                                      : "border-border/60 text-muted-foreground",
                                )}
                              >
                                {phase.label}
                              </div>
                            ))}
                          </div>
                        )}

                        {role.artifacts.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {role.artifacts.map((artifact) => (
                              <Button
                                key={artifact.filepath}
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-7 max-w-full min-w-0 px-2 text-xs"
                                onClick={() => openArtifact(artifact.filepath)}
                              >
                                <PackageCheckIcon className="size-3.5" />
                                <span className="truncate">
                                  {artifact.name}
                                </span>
                              </Button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })
            )}
          </section>

          {mappedArtifacts.length > 0 && (
            <section className="mt-5">
              <div className="text-muted-foreground mb-2 text-xs font-medium">
                {copy.deliverables}
              </div>
              <div className="space-y-2">
                {mappedArtifacts.map((artifact) => (
                  <button
                    key={artifact.filepath}
                    type="button"
                    className="border-border/80 hover:bg-accent/60 flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors"
                    onClick={() => openArtifact(artifact.filepath)}
                  >
                    <FileTextIcon className="text-muted-foreground size-4 shrink-0" />
                    <span className="min-w-0 flex-1 truncate">
                      {artifact.name}
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </aside>
  );
}
