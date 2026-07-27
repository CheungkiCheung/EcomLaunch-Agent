import type {
  CommerceCase,
  CommerceDomainEvent,
  CommerceRun,
  CommerceRunCheckpoint,
  CommerceRunDetail,
} from "./types";

export type CommerceWarRoomLaneStatus =
  | "completed"
  | "running"
  | "waiting"
  | "blocked"
  | "not_started";

export interface CommerceWarRoomViewModel {
  title: string;
  subtitle: string;
  items: Array<{
    id: string;
    caseId: string;
    caseTitle: string;
    title: string;
    statusLabel: string;
    updatedLabel: string;
  }>;
  selected: {
    id: string;
    caseId: string;
    caseTitle: string;
    title: string;
    statusLabel: string;
    shortId: string;
    latestEventLabel: string;
    quietLabel: string;
    summary: Array<{ label: string; valueLabel: string }>;
    lanes: Array<{
      key: string;
      title: string;
      status: CommerceWarRoomLaneStatus;
      statusLabel: string;
      description: string;
      eventLabel: string;
    }>;
    evidenceSummary: Array<{
      label: string;
      countLabel: string;
      tone: "support" | "contradict" | "unknown";
    }>;
    evidenceBoundaryLabel: string;
    checkpointLabel: string;
    eventItems: Array<{
      id: string;
      sequenceLabel: string;
      title: string;
      timeLabel: string;
      kind: "known" | "unknown";
    }>;
    wasReordered: boolean;
  } | null;
}

export function buildCommerceWarRoomViewModel({
  cases,
  runs,
  selectedRunId,
  selectedDetail,
  events,
  checkpoints,
}: {
  cases: CommerceCase[];
  runs: CommerceRun[];
  selectedRunId?: string | null;
  selectedDetail: CommerceRunDetail | null;
  events: CommerceDomainEvent[];
  checkpoints: CommerceRunCheckpoint[];
}): CommerceWarRoomViewModel {
  const caseMap = new Map(cases.map((item) => [item.id, item]));
  const orderedRuns = [...runs].sort(compareRunsForWarRoom);
  const items = orderedRuns.map((run) => ({
    id: run.id,
    caseId: run.case_id,
    caseTitle: localizedCaseTitle(caseMap.get(run.case_id)),
    title: localizedRunTitle(run),
    statusLabel: runStatusLabel(run.status),
    updatedLabel: formatTime(run.updated_at),
  }));
  const activeRunId =
    selectedRunId && items.some((item) => item.id === selectedRunId)
      ? selectedRunId
      : items[0]?.id;
  const activeRun = orderedRuns.find((item) => item.id === activeRunId) ?? null;
  const detail =
    activeRun && selectedDetail?.run.id === activeRun.id
      ? selectedDetail
      : activeRun
        ? { run: activeRun, latest_checkpoint: null }
        : null;
  const sorted = sortEvents(events);
  const relevantEvents = detail
    ? sorted.items.filter((item) => item.run_id === detail.run.id)
    : [];
  const latestCheckpoint =
    detail?.latest_checkpoint ??
    [...checkpoints].sort((left, right) => right.sequence - left.sequence)[0] ??
    null;
  return {
    title: "观察正在进行的调查",
    subtitle: "只展示已持久化的领域事件；没有新事件时保持安静。",
    items,
    selected: detail
      ? projectSelected(
          detail.run,
          caseMap.get(detail.run.case_id),
          relevantEvents,
          latestCheckpoint,
          sorted.wasReordered,
        )
      : null,
  };
}

function projectSelected(
  run: CommerceRun,
  commerceCase: CommerceCase | undefined,
  events: CommerceDomainEvent[],
  checkpoint: CommerceRunCheckpoint | null,
  wasReordered: boolean,
): NonNullable<CommerceWarRoomViewModel["selected"]> {
  const latestEvent = events.at(-1) ?? null;
  const lanes = buildLanes(run, events);
  const { limit, usage } = checkpoint?.checkpoint.budget_snapshot ?? {
    limit: null,
    usage: null,
  };
  return {
    id: run.id,
    caseId: run.case_id,
    caseTitle: localizedCaseTitle(commerceCase),
    title: localizedRunTitle(run),
    statusLabel: runStatusLabel(run.status),
    shortId: shortId(run.id),
    latestEventLabel: latestEvent
      ? `最新事件 #${latestEvent.run_sequence ?? "—"} · ${formatTime(latestEvent.occurred_at)}`
      : "尚无持久化事件",
    quietLabel: "等待下一条持久化事件",
    summary: [
      { label: "当前阶段", valueLabel: currentStageLabel(run, events) },
      {
        label: "循环",
        valueLabel:
          usage && limit
            ? `${usage.iterations} / ${limit.max_iterations}`
            : "未观察",
      },
      {
        label: "工具",
        valueLabel:
          usage && limit
            ? `${usage.tool_calls} / ${limit.max_tool_calls}`
            : "未观察",
      },
      {
        label: "路径",
        valueLabel:
          usage && limit
            ? `${usage.path_agents} / ${limit.max_path_agents}`
            : "未观察",
      },
    ],
    lanes,
    evidenceSummary: projectEvidenceSummary(events),
    evidenceBoundaryLabel: "未观察字段保持未知，不按零处理",
    checkpointLabel: checkpoint
      ? `最新检查点 #${checkpoint.sequence} · 循环 ${checkpoint.checkpoint.loop_iteration} · 证据 ${checkpoint.checkpoint.evidence_ids.length} · 工作假设 ${checkpoint.checkpoint.hypothesis_ids.length} · 上下文${checkpoint.checkpoint.context_sha256 ? "已记录" : "未观察"}`
      : "最新检查点未观察",
    eventItems: events.map((event) => {
      const knownTitle = eventTitle(event.event_type, event.payload);
      return {
        id: event.id,
        sequenceLabel: String(event.run_sequence ?? "—"),
        title: knownTitle ?? `未知事件：${event.event_type}`,
        timeLabel: formatTime(event.occurred_at),
        kind: knownTitle ? "known" : "unknown",
      };
    }),
    wasReordered,
  };
}

function buildLanes(run: CommerceRun, events: CommerceDomainEvent[]) {
  const goalEvent = events.find((item) => item.event_type === "run.created");
  const pathLanes = run.requested_paths.map((pathType) =>
    projectPathLane(pathType, events),
  );
  const allPathsTerminal = pathLanes.every((item) =>
    ["completed", "blocked"].includes(item.status),
  );
  const leadEvent = latestEventOfTypes(events, [
    "lead.started",
    "lead.completed",
    "lead.waiting",
    "lead.stopped",
  ]);
  const verificationEvent = latestEventOfTypes(events, [
    "verification.started",
    "verification.completed",
  ]);
  const barrierCompleted = allPathsTerminal && Boolean(leadEvent);
  return [
    {
      key: "goal",
      title: "目标循环",
      status: goalEvent ? ("completed" as const) : ("not_started" as const),
      statusLabel: goalEvent ? "已完成" : "未开始",
      description: goalEvent ? "目标已锁定" : "尚未创建运行",
      eventLabel: goalEvent ? eventSequenceLabel(goalEvent) : "尚未开始",
    },
    ...pathLanes,
    {
      key: "barrier",
      title: "证据屏障",
      status: barrierCompleted
        ? ("completed" as const)
        : pathLanes.some((item) => item.status === "running")
          ? ("waiting" as const)
          : pathLanes.some((item) => item.status === "blocked")
            ? ("blocked" as const)
            : ("not_started" as const),
      statusLabel: barrierCompleted
        ? "已放行"
        : pathLanes.some((item) => item.status === "running")
          ? "等待中"
          : pathLanes.some((item) => item.status === "blocked")
            ? "已阻塞"
            : "未开始",
      description: barrierCompleted
        ? "全部请求路径已进入终态，主智能体已启动"
        : "等待全部请求路径进入终态",
      eventLabel: barrierCompleted
        ? "由路径终态与主智能体事件确认"
        : "等待路径终态",
    },
    projectSynthesisVerificationLane(leadEvent, verificationEvent),
  ];
}

function projectPathLane(pathType: string, events: CommerceDomainEvent[]) {
  const completed = latestPathEvent(events, pathType, ["path.completed"]);
  const blocked = latestPathEvent(events, pathType, [
    "path.blocked",
    "path.failed",
  ]);
  const started = latestPathEvent(events, pathType, ["path.started"]);
  const event = completed ?? blocked ?? started;
  const status: CommerceWarRoomLaneStatus = completed
    ? "completed"
    : blocked
      ? "blocked"
      : started
        ? "running"
        : "not_started";
  const evidenceIds = Array.isArray(completed?.payload.evidence_ids)
    ? completed.payload.evidence_ids.filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  return {
    key: pathType,
    title: pathLabel(pathType),
    status,
    statusLabel: laneStatusLabel(status),
    description: completed
      ? `已完成 · ${evidenceIds.length > 0 ? `${evidenceIds.length} 条证据` : "证据数量未观察"}`
      : blocked
        ? blockedPathDescription(pathType, blocked.payload.reason)
        : started
          ? runningPathDescription(pathType)
          : "尚未开始",
    eventLabel: event ? eventSequenceLabel(event) : "尚未开始",
  };
}

function projectSynthesisVerificationLane(
  leadEvent: CommerceDomainEvent | null,
  verificationEvent: CommerceDomainEvent | null,
) {
  if (verificationEvent?.event_type === "verification.completed") {
    return {
      key: "synthesis_verification",
      title: "主智能体综合 / 新鲜上下文验证",
      status: "completed" as const,
      statusLabel: "已完成",
      description: "主智能体综合与独立验证已完成",
      eventLabel: eventSequenceLabel(verificationEvent),
    };
  }
  if (verificationEvent) {
    return {
      key: "synthesis_verification",
      title: "主智能体综合 / 新鲜上下文验证",
      status: "running" as const,
      statusLabel: "进行中",
      description: "新鲜上下文验证已启动",
      eventLabel: eventSequenceLabel(verificationEvent),
    };
  }
  if (leadEvent) {
    const waiting = leadEvent.event_type === "lead.waiting";
    return {
      key: "synthesis_verification",
      title: "主智能体综合 / 新鲜上下文验证",
      status: waiting ? ("waiting" as const) : ("running" as const),
      statusLabel: waiting ? "等待中" : "进行中",
      description: waiting ? "主智能体正在等待外部输入" : "主智能体综合已启动",
      eventLabel: eventSequenceLabel(leadEvent),
    };
  }
  return {
    key: "synthesis_verification",
    title: "主智能体综合 / 新鲜上下文验证",
    status: "not_started" as const,
    statusLabel: "未开始",
    description: "尚未开始",
    eventLabel: "尚未开始",
  };
}

function projectEvidenceSummary(events: CommerceDomainEvent[]) {
  const evidence = new Map<string, string>();
  for (const event of events) {
    if (event.event_type !== "evidence.appended") continue;
    const evidenceId = event.payload.evidence_id;
    const relation = event.payload.relation;
    if (typeof evidenceId === "string" && typeof relation === "string") {
      evidence.set(evidenceId, relation);
    }
  }
  const values = [...evidence.values()];
  return [
    {
      label: "支持",
      countLabel: String(values.filter((item) => item === "supports").length),
      tone: "support" as const,
    },
    {
      label: "矛盾",
      countLabel: String(
        values.filter((item) => item === "contradicts").length,
      ),
      tone: "contradict" as const,
    },
    {
      label: "未知",
      countLabel: String(
        values.filter((item) => !["supports", "contradicts"].includes(item))
          .length,
      ),
      tone: "unknown" as const,
    },
  ];
}

function currentStageLabel(run: CommerceRun, events: CommerceDomainEvent[]) {
  if (hasEvent(events, "verification.started")) return "新鲜上下文验证";
  if (hasEvent(events, "lead.started")) return "主智能体综合";
  if (
    run.requested_paths.some((path) =>
      latestPathEvent(events, path, ["path.started"]),
    )
  ) {
    return "并行路径";
  }
  return run.phase === "planning" ? "能力路由" : "目标循环";
}

function eventTitle(eventType: string, payload: Record<string, unknown>) {
  const pathType =
    typeof payload.path_type === "string" ? payload.path_type : null;
  const path = pathType ? pathLabel(pathType) : "路径";
  return {
    "run.created": "运行已创建",
    "run.phase_changed": "运行阶段已变化",
    "run.status_changed": "运行状态已变化",
    "run.updated": "运行记录已更新",
    "run.checkpoint_saved": "检查点已保存",
    "run.lease_released": "运行资源已释放",
    "path.started": `${path}已启动`,
    "path.completed": `${path}已完成`,
    "path.blocked": `${path}已阻塞`,
    "path.failed": `${path}失败`,
    "evidence.appended": "证据已持久化",
    "lead.started": "主智能体综合已启动",
    "lead.completed": "主智能体综合已完成",
    "lead.waiting": "主智能体进入等待",
    "lead.stopped": "主智能体已停止",
    "verification.started": "新鲜上下文验证已启动",
    "verification.completed": "新鲜上下文验证已完成",
  }[eventType];
}

function sortEvents(events: CommerceDomainEvent[]) {
  const items = [...events].sort((left, right) => {
    if (left.run_sequence !== null && right.run_sequence !== null) {
      return left.run_sequence - right.run_sequence;
    }
    return Date.parse(left.occurred_at) - Date.parse(right.occurred_at);
  });
  return {
    items,
    wasReordered: items.some((item, index) => item.id !== events[index]?.id),
  };
}

function compareRunsForWarRoom(left: CommerceRun, right: CommerceRun) {
  const leftPriority = runPriority(left.status);
  const rightPriority = runPriority(right.status);
  return (
    rightPriority - leftPriority ||
    Date.parse(right.updated_at) - Date.parse(left.updated_at)
  );
}

function runPriority(status: string) {
  if (status === "running") return 3;
  if (status === "waiting" || status === "queued") return 2;
  return 1;
}

function latestPathEvent(
  events: CommerceDomainEvent[],
  pathType: string,
  types: string[],
) {
  return [...events]
    .reverse()
    .find(
      (event) =>
        types.includes(event.event_type) &&
        event.payload.path_type === pathType,
    );
}

function latestEventOfTypes(events: CommerceDomainEvent[], types: string[]) {
  return (
    [...events].reverse().find((event) => types.includes(event.event_type)) ??
    null
  );
}

function hasEvent(events: CommerceDomainEvent[], eventType: string) {
  return events.some((event) => event.event_type === eventType);
}

function eventSequenceLabel(event: CommerceDomainEvent) {
  return event.run_sequence === null
    ? "事件序号未观察"
    : `事件 #${event.run_sequence}`;
}

function pathLabel(pathType: string) {
  return (
    {
      fulfillment: "履约路径",
      seller_peer: "卖家对标",
      review_experience: "评价体验",
    }[pathType] ?? "未知路径"
  );
}

function runningPathDescription(pathType: string) {
  return (
    {
      fulfillment: "正在读取履约事实",
      seller_peer: "正在读取同类卖家对标",
      review_experience: "正在读取评价体验数据",
    }[pathType] ?? "路径已启动"
  );
}

function blockedPathDescription(pathType: string, reason: unknown) {
  if (pathType === "review_experience" && reason === "missing_review_text") {
    return "缺少评价文本，路径已阻塞";
  }
  return "路径已阻塞，等待明确恢复条件";
}

function laneStatusLabel(status: CommerceWarRoomLaneStatus) {
  return {
    completed: "已完成",
    running: "进行中",
    waiting: "等待中",
    blocked: "已阻塞",
    not_started: "未开始",
  }[status];
}

function runStatusLabel(status: string) {
  return (
    {
      queued: "排队中",
      running: "进行中",
      waiting: "等待中",
      completed: "已完成",
      failed: "失败",
      timeout: "已超时",
      cancelled: "已取消",
      blocked: "已阻塞",
    }[status] ?? "状态待确认"
  );
}

function localizedRunTitle(run: CommerceRun) {
  if (/\p{Script=Han}/u.test(run.goal)) return run.goal;
  const normalized = run.goal.toLowerCase();
  if (normalized.includes("fulfillment") || normalized.includes("delivery")) {
    return "调查履约延迟原因";
  }
  if (normalized.includes("review")) return "调查评价体验问题";
  if (normalized.includes("peer")) return "调查卖家对标差异";
  return "观察经营诊断运行";
}

function localizedCaseTitle(item: CommerceCase | undefined) {
  if (!item) return "案例标题不可用";
  if (/\p{Script=Han}/u.test(item.title)) return item.title;
  const source = `${item.title} ${item.summary ?? ""}`.toLowerCase();
  if (
    source.includes("fulfillment") ||
    source.includes("delivery") ||
    source.includes("履约")
  ) {
    return "履约延迟异常";
  }
  if (source.includes("review") || source.includes("评价"))
    return "评价体验异常";
  return "经营诊断案例";
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function shortId(value: string) {
  return value.length <= 14 ? value : `${value.slice(0, 4)}…${value.slice(-6)}`;
}
