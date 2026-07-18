import type { Todo } from "@/core/todos";
import { getFileName } from "@/core/utils/files";

export type LaunchCrewRole =
  | "launch-director"
  | "market-voc-researcher"
  | "offer-architect"
  | "growth-analyst"
  | "asset-studio"
  | "evidence-checker";

export type LaunchCrewTaskStatus = "in_progress" | "completed" | "failed";
export type LaunchCrewAgentStatus =
  | "idle"
  | "working"
  | "searching"
  | "reading"
  | "writing"
  | "done"
  | "delivered"
  | "error";
export type LaunchCrewArtifactStatus = "pending" | "ready";
export type LaunchCrewBadgeStatus = "pending" | "active" | "ready" | "info";
export type LaunchCrewMissionStatus = "active" | "pending" | "done";

export type LaunchCrewTask = {
  id: string;
  role: LaunchCrewRole;
  status: LaunchCrewTaskStatus;
  description: string;
  prompt: string;
  result?: string;
  error?: string;
  currentAction?: string | null;
  toolName?: string | null;
};

export type LaunchCrewArtifact = {
  filepath: string;
  name: string;
  role: LaunchCrewRole;
  status: LaunchCrewArtifactStatus;
  label: string;
  required: boolean;
};

export type LaunchCrewAgent = {
  id: LaunchCrewRole;
  name: string;
  shortName: string;
  label: string;
  desk: string;
  accent: "amber" | "blue" | "cyan" | "emerald" | "rose" | "sky";
  initial: string;
  status: LaunchCrewAgentStatus;
  active: boolean;
  selected: boolean;
  currentAction?: string | null;
  lastLine: string;
  task?: LaunchCrewTask;
  artifacts: LaunchCrewArtifact[];
};

export type LaunchCrewCommsEvent = {
  id: string;
  role: LaunchCrewRole;
  speaker: string;
  text: string;
  kind: "task" | "result" | "error" | "artifact";
};

export type LaunchCrewMission = {
  id: string;
  label: string;
  status: LaunchCrewMissionStatus;
  role?: LaunchCrewRole;
};

export type LaunchCrewEvidenceBadge = {
  id: string;
  label: string;
  status: LaunchCrewBadgeStatus;
};

export type LaunchLoopSnapshot = {
  stage: string;
  decision: string;
  status: LaunchCrewMissionStatus | "failed";
  privateMetricBoundary: LaunchCrewEvidenceBadge;
  coreArtifacts: LaunchCrewArtifact[];
  loopArtifacts: LaunchCrewArtifact[];
  readyArtifactCount: number;
  totalArtifactCount: number;
};

export type LaunchCrewActivityModel = {
  agents: LaunchCrewAgent[];
  selectedAgent: LaunchCrewAgent;
  liveComms: LaunchCrewCommsEvent[];
  activeMissions: LaunchCrewMission[];
  artifactStatuses: LaunchCrewArtifact[];
  evidenceBadges: LaunchCrewEvidenceBadge[];
  loopSnapshot: LaunchLoopSnapshot;
  activeAgentCount: number;
  completedAgentCount: number;
  progress: number;
};

export type BuildLaunchCrewActivityInput = {
  tasks: LaunchCrewTask[];
  artifacts: string[];
  todos?: Todo[];
  selectedAgentId?: LaunchCrewRole | null;
  finalResponseText?: string;
  isStreaming: boolean;
};

export const LAUNCH_CREW_AGENTS: Array<
  Omit<
    LaunchCrewAgent,
    | "status"
    | "active"
    | "selected"
    | "lastLine"
    | "task"
    | "artifacts"
    | "currentAction"
  >
> = [
  {
    id: "market-voc-researcher",
    name: "Market & VOC Researcher",
    shortName: "Market Scout",
    label: "市场与 VOC",
    desk: "公开信号与用户声音",
    accent: "cyan",
    initial: "M",
  },
  {
    id: "offer-architect",
    name: "Offer Architect",
    shortName: "Offer Architect",
    label: "定位与验证",
    desk: "首个 offer wedge",
    accent: "emerald",
    initial: "O",
  },
  {
    id: "launch-director",
    name: "Launch Director",
    shortName: "Launch Director",
    label: "总控调度",
    desk: "任务拆解与合成",
    accent: "blue",
    initial: "D",
  },
  {
    id: "evidence-checker",
    name: "Evidence Checker",
    shortName: "Evidence Checker",
    label: "证据与口径",
    desk: "claim readiness",
    accent: "sky",
    initial: "E",
  },
  {
    id: "growth-analyst",
    name: "Growth Analyst",
    shortName: "Growth Analyst",
    label: "增长实验",
    desk: "指标与实验读数",
    accent: "amber",
    initial: "G",
  },
  {
    id: "asset-studio",
    name: "Asset Studio",
    shortName: "Asset Studio",
    label: "内容资产",
    desk: "listing 与内容包",
    accent: "rose",
    initial: "A",
  },
];

type LaunchDeliverableGroup = "core" | "loop" | "calibration";

const LAUNCH_DELIVERABLES: Array<{
  filepath: string;
  label: string;
  role: LaunchCrewRole;
  required: boolean;
  group: LaunchDeliverableGroup;
}> = [
  {
    filepath: "competitor-table.csv",
    label: "市场信号表",
    role: "market-voc-researcher",
    required: true,
    group: "core",
  },
  {
    filepath: "evidence-ledger.json",
    label: "证据账本",
    role: "evidence-checker",
    required: true,
    group: "core",
  },
  {
    filepath: "positioning-brief.md",
    label: "定位 brief",
    role: "offer-architect",
    required: true,
    group: "core",
  },
  {
    filepath: "listing-pack.md",
    label: "Listing pack",
    role: "asset-studio",
    required: true,
    group: "core",
  },
  {
    filepath: "content-pack.md",
    label: "内容包",
    role: "asset-studio",
    required: true,
    group: "core",
  },
  {
    filepath: "launch-calendar.csv",
    label: "下一轮计划",
    role: "growth-analyst",
    required: true,
    group: "core",
  },
  {
    filepath: "launch-war-room.html",
    label: "War room 页面",
    role: "evidence-checker",
    required: true,
    group: "core",
  },
  {
    filepath: "launch-state.json",
    label: "循环状态",
    role: "launch-director",
    required: false,
    group: "loop",
  },
  {
    filepath: "promotion-replan.md",
    label: "推广重排",
    role: "growth-analyst",
    required: false,
    group: "loop",
  },
  {
    filepath: "knowledge-deltas.json",
    label: "知识增量",
    role: "evidence-checker",
    required: false,
    group: "loop",
  },
  {
    filepath: "calibration-ledger.json",
    label: "校准账本",
    role: "evidence-checker",
    required: false,
    group: "calibration",
  },
  {
    filepath: "rubric.md",
    label: "评分公式",
    role: "evidence-checker",
    required: false,
    group: "calibration",
  },
  {
    filepath: "content-scorecard.md",
    label: "内容评分卡",
    role: "asset-studio",
    required: false,
    group: "calibration",
  },
];

const ARTIFACT_ROLE_OVERRIDES = new Map(
  LAUNCH_DELIVERABLES.map((artifact) => [artifact.filepath, artifact.role]),
);

export function buildLaunchCrewActivityModel({
  tasks,
  artifacts,
  todos,
  selectedAgentId,
  finalResponseText,
  isStreaming,
}: BuildLaunchCrewActivityInput): LaunchCrewActivityModel {
  const taskByRole = latestTaskByRole(tasks);
  const artifactStatuses = buildArtifacts(artifacts);
  const artifactsByRole = groupArtifactsByRole(artifactStatuses);
  const selectedFallback = chooseSelectedAgentId({
    selectedAgentId,
    tasks,
    artifactsByRole,
    isStreaming,
  });

  const agents = LAUNCH_CREW_AGENTS.map((config) => {
    const task = taskByRole.get(config.id);
    const roleArtifacts = artifactsByRole.get(config.id) ?? [];
    const status = statusForAgent(config.id, task, roleArtifacts, isStreaming);
    return {
      ...config,
      status,
      active: status !== "idle",
      selected: config.id === selectedFallback,
      currentAction: task?.currentAction ?? null,
      lastLine: lineForAgent(config.id, task, status, roleArtifacts.length),
      task,
      artifacts: roleArtifacts,
    };
  });
  const selectedAgent =
    agents.find((agent) => agent.id === selectedFallback) ??
    agents.find((agent) => agent.id === "launch-director") ??
    agents[0]!;
  const completedAgentCount = agents.filter(
    (agent) => agent.status === "done" || agent.status === "delivered",
  ).length;
  const activeAgentCount = agents.filter((agent) => agent.active).length;

  return {
    agents,
    selectedAgent,
    liveComms: buildLiveComms(tasks, artifactStatuses),
    activeMissions: buildActiveMissions(tasks, artifactStatuses, todos),
    artifactStatuses,
    evidenceBadges: buildEvidenceBadges(tasks, artifactStatuses, isStreaming),
    loopSnapshot: buildLoopSnapshot({
      tasks,
      artifacts: artifactStatuses,
      finalResponseText,
      isStreaming,
    }),
    activeAgentCount,
    completedAgentCount,
    progress:
      activeAgentCount === 0
        ? 0
        : Math.round((completedAgentCount / activeAgentCount) * 100),
  };
}

function latestTaskByRole(tasks: LaunchCrewTask[]) {
  const result = new Map<LaunchCrewRole, LaunchCrewTask>();
  for (const task of tasks) {
    result.set(task.role, task);
  }
  return result;
}

function buildArtifacts(filepaths: string[]): LaunchCrewArtifact[] {
  const readyByName = new Map(
    filepaths.map((filepath) => [getFileName(filepath), filepath]),
  );
  const known = LAUNCH_DELIVERABLES.map((deliverable) => ({
    filepath: readyByName.get(deliverable.filepath) ?? deliverable.filepath,
    name: deliverable.filepath,
    label: deliverable.label,
    role: deliverable.role,
    required: deliverable.required,
    status: readyByName.has(deliverable.filepath) ? "ready" : "pending",
  })) satisfies LaunchCrewArtifact[];
  const extra = filepaths
    .map((filepath) => {
      const name = getFileName(filepath);
      return { filepath, name };
    })
    .filter(
      ({ name }) => !LAUNCH_DELIVERABLES.some((item) => item.filepath === name),
    )
    .map(({ filepath, name }) => ({
      filepath,
      name,
      label: name,
      role: roleForArtifactName(name),
      required: false,
      status: "ready" as const,
    }));
  return [...known, ...extra];
}

function roleForArtifactName(name: string): LaunchCrewRole {
  return ARTIFACT_ROLE_OVERRIDES.get(name) ?? "launch-director";
}

function groupArtifactsByRole(artifacts: LaunchCrewArtifact[]) {
  const result = new Map<LaunchCrewRole, LaunchCrewArtifact[]>();
  for (const artifact of artifacts) {
    if (artifact.status !== "ready") {
      continue;
    }
    const current = result.get(artifact.role) ?? [];
    current.push(artifact);
    result.set(artifact.role, current);
  }
  return result;
}

function statusForAgent(
  role: LaunchCrewRole,
  task: LaunchCrewTask | undefined,
  artifacts: LaunchCrewArtifact[],
  isStreaming: boolean,
): LaunchCrewAgentStatus {
  if (role === "launch-director" && isStreaming) {
    return "working";
  }
  if (task?.status === "failed") {
    return "error";
  }
  if (task?.status === "completed") {
    return artifacts.length > 0 ? "done" : "done";
  }
  if (task?.status === "in_progress") {
    if (task.toolName === "web_search" || task.toolName === "image_search") {
      return "searching";
    }
    if (task.toolName === "web_fetch" || task.toolName === "read_file") {
      return "reading";
    }
    if (task.toolName === "write_file" || task.toolName === "present_files") {
      return "writing";
    }
    return "working";
  }
  if (artifacts.length > 0) {
    return "delivered";
  }
  return "idle";
}

function lineForAgent(
  role: LaunchCrewRole,
  task: LaunchCrewTask | undefined,
  status: LaunchCrewAgentStatus,
  artifactCount: number,
) {
  if (task?.status === "failed") {
    return task.error ?? "这个工作流遇到阻塞。";
  }
  if (task?.currentAction) {
    return task.currentAction;
  }
  if (task?.status === "completed") {
    return task.result
      ? "结构化发现已回传给 Launch Director。"
      : "子任务已完成。";
  }
  if (task) {
    return task.description;
  }
  if (artifactCount > 0) {
    return "交付物已落地。";
  }
  if (role === "launch-director" && status === "working") {
    return "正在调度 Launch Crew。";
  }
  return "等待 Launch Director 分派任务。";
}

function chooseSelectedAgentId({
  selectedAgentId,
  tasks,
  artifactsByRole,
  isStreaming,
}: {
  selectedAgentId?: LaunchCrewRole | null;
  tasks: LaunchCrewTask[];
  artifactsByRole: Map<LaunchCrewRole, LaunchCrewArtifact[]>;
  isStreaming: boolean;
}) {
  const validSelection =
    selectedAgentId &&
    selectedAgentId !== "launch-director" &&
    (tasks.some((task) => task.role === selectedAgentId) ||
      (artifactsByRole.get(selectedAgentId)?.length ?? 0) > 0);
  if (validSelection) {
    return selectedAgentId;
  }
  const failed = [...tasks].reverse().find((task) => task.status === "failed");
  if (failed) {
    return failed.role;
  }
  const working = [...tasks]
    .reverse()
    .find((task) => task.status === "in_progress");
  if (working) {
    return working.role;
  }
  const completed = [...tasks]
    .reverse()
    .find((task) => task.status === "completed");
  if (completed) {
    return completed.role;
  }
  if (isStreaming) {
    return "launch-director";
  }
  return "launch-director";
}

function buildLiveComms(
  tasks: LaunchCrewTask[],
  artifacts: LaunchCrewArtifact[],
): LaunchCrewCommsEvent[] {
  const taskEvents = tasks.map((task) => ({
    id: `task-${task.id}`,
    role: task.role,
    speaker: agentName(task.role),
    text:
      task.status === "failed"
        ? (task.error ?? "任务阻塞")
        : task.status === "completed"
          ? task.result
            ? "结构化发现已回传。"
            : "子任务已完成。"
          : (task.currentAction ?? task.description),
    kind:
      task.status === "failed"
        ? ("error" as const)
        : task.status === "completed"
          ? ("result" as const)
          : ("task" as const),
  }));
  const artifactEvents = artifacts
    .filter((artifact) => artifact.status === "ready")
    .map((artifact) => ({
      id: `artifact-${artifact.filepath}`,
      role: artifact.role,
      speaker: agentName(artifact.role),
      text: `${artifact.name} 已落地`,
      kind: "artifact" as const,
    }));
  return [...taskEvents, ...artifactEvents].slice(-5);
}

function buildActiveMissions(
  tasks: LaunchCrewTask[],
  artifacts: LaunchCrewArtifact[],
  todos: Todo[] | undefined,
): LaunchCrewMission[] {
  const missions: LaunchCrewMission[] = [];
  for (const [index, todo] of (todos ?? []).entries()) {
    if (todo.status !== "in_progress" || !todo.content) {
      continue;
    }
    missions.push({
      id: `todo-${index}-${todo.content}`,
      label: todo.content,
      status: "active",
    });
  }
  for (const task of tasks.filter((item) => item.status === "in_progress")) {
    missions.push({
      id: `task-${task.id}`,
      label: task.description,
      status: "active",
      role: task.role,
    });
  }
  for (const artifact of artifacts.filter((item) => item.status === "ready")) {
    missions.push({
      id: `artifact-${artifact.filepath}`,
      label: artifact.label,
      status: "done",
      role: artifact.role,
    });
  }
  return dedupeMissions(missions).slice(0, 6);
}

function dedupeMissions(missions: LaunchCrewMission[]) {
  const seen = new Set<string>();
  const result: LaunchCrewMission[] = [];
  for (const mission of missions) {
    const key = mission.label.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(mission);
  }
  return result;
}

function buildEvidenceBadges(
  tasks: LaunchCrewTask[],
  artifacts: LaunchCrewArtifact[],
  isStreaming: boolean,
): LaunchCrewEvidenceBadge[] {
  const artifactNames = new Set(
    artifacts
      .filter((artifact) => artifact.status === "ready")
      .map((artifact) => artifact.name),
  );
  const evidenceTask = tasks.find((task) => task.role === "evidence-checker");
  return [
    {
      id: "evidence-ledger",
      label: "证据账本",
      status: artifactNames.has("evidence-ledger.json") ? "ready" : "pending",
    },
    {
      id: "claims-audit",
      label: "口径审计",
      status: artifactNames.has("evidence-ledger.json")
        ? "ready"
        : evidenceTask || isStreaming
          ? "active"
          : "pending",
    },
    {
      id: "private-metrics",
      label: "私域指标 unavailable",
      status: "info",
    },
    {
      id: "artifacts",
      label: "交付物",
      status: artifacts.some((artifact) => artifact.status === "ready")
        ? "active"
        : "pending",
    },
  ];
}

function buildLoopSnapshot({
  tasks,
  artifacts,
  finalResponseText,
  isStreaming,
}: {
  tasks: LaunchCrewTask[];
  artifacts: LaunchCrewArtifact[];
  finalResponseText?: string;
  isStreaming: boolean;
}): LaunchLoopSnapshot {
  const readyArtifacts = artifacts.filter(
    (artifact) => artifact.status === "ready",
  );
  const failed = tasks.some((task) => task.status === "failed");
  const stage = extractStage(finalResponseText) ?? "待诊断";
  const decision =
    extractDecision(finalResponseText) ?? (isStreaming ? "判断中" : "待决策");
  const coreArtifacts = artifacts.filter(
    (artifact) => deliverableGroup(artifact.name) === "core",
  );
  const loopArtifacts = artifacts.filter(
    (artifact) => deliverableGroup(artifact.name) === "loop",
  );
  const hasDecisionEvidence =
    decision !== "待决策" ||
    readyArtifacts.some((artifact) => artifact.name === "launch-state.json");

  return {
    stage,
    decision,
    status: failed
      ? "failed"
      : hasDecisionEvidence
        ? "done"
        : isStreaming
          ? "active"
          : "pending",
    privateMetricBoundary: {
      id: "private-metrics",
      label: "GMV/CTR/CVR/ROI unavailable unless uploaded",
      status: "info",
    },
    coreArtifacts,
    loopArtifacts,
    readyArtifactCount: readyArtifacts.length,
    totalArtifactCount: artifacts.length,
  };
}

function deliverableGroup(name: string): LaunchDeliverableGroup | null {
  return (
    LAUNCH_DELIVERABLES.find((deliverable) => deliverable.filepath === name)
      ?.group ?? null
  );
}

function extractStage(text: string | undefined) {
  if (!text) {
    return null;
  }
  const lower = text.toLowerCase();
  const stages = [
    "idea_only",
    "supplier_sample",
    "pre_launch_test",
    "soft_launch",
    "scale_iterate",
  ];
  return stages.find((stage) => lower.includes(stage)) ?? null;
}

function extractDecision(text: string | undefined) {
  if (!text) {
    return null;
  }
  const match = text.match(/\b(go|pivot|hold|kill|scale)\b/i);
  if (!match) {
    return null;
  }
  return match[1]!.slice(0, 1).toUpperCase() + match[1]!.slice(1).toLowerCase();
}

function agentName(role: LaunchCrewRole) {
  return (
    LAUNCH_CREW_AGENTS.find((agent) => agent.id === role)?.shortName ?? role
  );
}
