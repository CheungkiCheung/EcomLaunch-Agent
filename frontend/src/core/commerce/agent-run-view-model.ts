import type {
  CommerceCase,
  CommerceDomainEvent,
  CommerceRun,
  CommerceRunCheckpoint,
  CommerceRunDetail,
} from "./types";

export type CommerceRunFilter =
  | "all"
  | "running"
  | "waiting"
  | "completed"
  | "failed";

export type CommerceRunStageStatus =
  | "completed"
  | "running"
  | "waiting"
  | "blocked"
  | "not_started";

export interface CommerceRunPathViewModel {
  pathType: string;
  label: string;
  status: CommerceRunStageStatus;
  statusLabel: string;
  evidenceCountLabel: string;
}

export interface CommerceRunStageViewModel {
  key: string;
  title: string;
  description: string;
  status: CommerceRunStageStatus;
  statusLabel: string;
  kind: "step" | "fanout";
  paths: CommerceRunPathViewModel[];
  derivationLabel: string | null;
}

export interface CommerceRunQueueItemViewModel {
  id: string;
  caseId: string;
  caseTitle: string;
  title: string;
  statusLabel: string;
  statusGroup: Exclude<CommerceRunFilter, "all">;
  typeLabel: string;
  timeLabel: string;
  pathCountLabel: string;
  stopReasonLabel: string;
}

export interface CommerceAgentRunDetailViewModel extends CommerceRunQueueItemViewModel {
  shortId: string;
  goal: string;
  durationLabel: string;
  periodLabel: string;
  stages: CommerceRunStageViewModel[];
  telemetry: {
    modelIdentityLabel: string;
    requestCountLabel: string;
    tokenLabel: string;
    latencyLabel: string;
    retryLabel: string;
    stopReasonLabel: string;
  };
  budget: Array<{
    label: string;
    valueLabel: string;
    ratio: number;
  }>;
  checkpoint: {
    sequenceLabel: string;
    iterationLabel: string;
    evidenceLabel: string;
    hypothesisLabel: string;
    contextLabel: string;
  } | null;
  selectedStageTitle: string;
  selectedStageDescription: string;
  eventCountLabel: string;
  checkpointCountLabel: string;
  auditBoundary: string;
  events: Array<{
    id: string;
    sequenceLabel: string;
    title: string;
    timeLabel: string;
  }>;
  checkpoints: Array<{
    id: string;
    sequenceLabel: string;
    iterationLabel: string;
    evidenceLabel: string;
    hypothesisLabel: string;
    createdLabel: string;
  }>;
  wasReordered: boolean;
}

export interface CommerceAgentRunViewModel {
  title: string;
  subtitle: string;
  filters: Array<{
    value: CommerceRunFilter;
    label: string;
    count: number;
  }>;
  items: CommerceRunQueueItemViewModel[];
  selected: CommerceAgentRunDetailViewModel | null;
}

export function buildCommerceAgentRunViewModel({
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
}): CommerceAgentRunViewModel {
  const caseMap = new Map(cases.map((item) => [item.id, item]));
  const items = [...runs]
    .sort(
      (left, right) =>
        Date.parse(right.updated_at) - Date.parse(left.updated_at),
    )
    .map((run) => projectRunQueueItem(run, caseMap));
  const activeRunId =
    selectedRunId && items.some((item) => item.id === selectedRunId)
      ? selectedRunId
      : items[0]?.id;
  const activeRun = runs.find((item) => item.id === activeRunId);
  const detail =
    selectedDetail?.run.id === activeRunId
      ? selectedDetail
      : activeRun
        ? { run: activeRun, latest_checkpoint: null }
        : null;
  return {
    title: "检查一次智能体运行",
    subtitle: "所有状态来自运行、检查点和领域事件，不从对话或动画推断。",
    filters: [
      runFilter("all", "全部", items),
      runFilter("running", "进行中", items),
      runFilter("waiting", "等待中", items),
      runFilter("completed", "已完成", items),
      runFilter("failed", "失败", items),
    ],
    items,
    selected: detail
      ? projectRunDetail(detail, caseMap, events, checkpoints)
      : null,
  };
}

export function filterCommerceRunItems(
  items: readonly CommerceRunQueueItemViewModel[],
  options: { filter: CommerceRunFilter; query: string },
): CommerceRunQueueItemViewModel[] {
  const query = options.query.trim().toLocaleLowerCase("zh-CN");
  return items.filter((item) => {
    if (options.filter !== "all" && item.statusGroup !== options.filter) {
      return false;
    }
    if (!query) return true;
    return [item.title, item.caseTitle, item.typeLabel, item.statusLabel]
      .join(" ")
      .toLocaleLowerCase("zh-CN")
      .includes(query);
  });
}

function runFilter(
  value: CommerceRunFilter,
  label: string,
  items: readonly CommerceRunQueueItemViewModel[],
) {
  return {
    value,
    label,
    count:
      value === "all"
        ? items.length
        : items.filter((item) => item.statusGroup === value).length,
  };
}

function projectRunQueueItem(
  run: CommerceRun,
  cases: Map<string, CommerceCase>,
): CommerceRunQueueItemViewModel {
  return {
    id: run.id,
    caseId: run.case_id,
    caseTitle: localizedCaseTitle(cases.get(run.case_id)),
    title: localizedRunTitle(run),
    statusLabel: runStatusLabel(run.status),
    statusGroup: runStatusGroup(run.status),
    typeLabel: runTypeLabel(run.run_type),
    timeLabel: formatTime(run.updated_at),
    pathCountLabel:
      run.requested_paths.length > 0
        ? `${run.requested_paths.length} 条路径`
        : "没有 Path 路由",
    stopReasonLabel: run.stop_reason
      ? stopReasonLabel(run.stop_reason)
      : run.wait_reason
        ? waitReasonLabel(run.wait_reason)
        : "尚无停止原因",
  };
}

function projectRunDetail(
  detail: CommerceRunDetail,
  cases: Map<string, CommerceCase>,
  rawEvents: CommerceDomainEvent[],
  checkpoints: CommerceRunCheckpoint[],
): CommerceAgentRunDetailViewModel {
  const base = projectRunQueueItem(detail.run, cases);
  const sortedEventsResult = sortRunEvents(rawEvents);
  const sortedEvents = sortedEventsResult.items;
  const latestCheckpoint =
    detail.latest_checkpoint ??
    [...checkpoints].sort((left, right) => right.sequence - left.sequence)[0] ??
    null;
  const stages = buildRunStages(detail.run, sortedEvents);
  const telemetry = aggregateTelemetry(sortedEvents);
  const selectedStage =
    stages.find(
      (item) => item.key === "verification" && item.status === "completed",
    ) ??
    [...stages]
      .reverse()
      .find((item) => item.key !== "stop" && item.status === "completed") ??
    stages[0];
  return {
    ...base,
    shortId: shortId(detail.run.id),
    goal: localizedGoal(detail.run.goal),
    durationLabel: runDurationLabel(detail.run),
    periodLabel: runPeriodLabel(detail.run),
    stages,
    telemetry,
    budget: latestCheckpoint ? projectBudget(latestCheckpoint) : [],
    checkpoint: latestCheckpoint
      ? {
          sequenceLabel: String(latestCheckpoint.sequence),
          iterationLabel: String(latestCheckpoint.checkpoint.loop_iteration),
          evidenceLabel: String(
            latestCheckpoint.checkpoint.evidence_ids.length,
          ),
          hypothesisLabel: String(
            latestCheckpoint.checkpoint.hypothesis_ids.length,
          ),
          contextLabel: latestCheckpoint.checkpoint.context_sha256
            ? "已记录"
            : "未观察",
        }
      : null,
    selectedStageTitle: selectedStage?.title ?? "运行详情",
    selectedStageDescription:
      selectedStage?.key === "verification"
        ? "验证器不继承主智能体的完整推理历史，只读取最小可审计上下文。"
        : (selectedStage?.description ?? "当前没有可展示的阶段详情。"),
    eventCountLabel: `${sortedEvents.length} 条事件`,
    checkpointCountLabel: `${checkpoints.length} 个检查点`,
    auditBoundary:
      "提供方请求编号、实际模型、令牌用量、延迟和重试均来自真实领域事件；无事件时显示未观察。",
    events: sortedEvents.map((event) => ({
      id: event.id,
      sequenceLabel:
        event.run_sequence === null ? "—" : String(event.run_sequence),
      title: eventTitle(event.event_type),
      timeLabel: formatTime(event.occurred_at),
    })),
    checkpoints: [...checkpoints]
      .sort((left, right) => right.sequence - left.sequence)
      .map((item) => ({
        id: item.id,
        sequenceLabel: String(item.sequence),
        iterationLabel: String(item.checkpoint.loop_iteration),
        evidenceLabel: String(item.checkpoint.evidence_ids.length),
        hypothesisLabel: String(item.checkpoint.hypothesis_ids.length),
        createdLabel: formatDateTime(item.created_at),
      })),
    wasReordered: sortedEventsResult.wasReordered,
  };
}

function buildRunStages(
  run: CommerceRun,
  events: CommerceDomainEvent[],
): CommerceRunStageViewModel[] {
  if (
    run.requested_paths.length === 0 &&
    !["case_investigation", "replan"].includes(run.run_type)
  ) {
    return buildGenericRunStages(run, events);
  }
  const pathViews = run.requested_paths.map((pathType) =>
    projectPath(pathType, events),
  );
  const allPathsTerminal = pathViews.every((item) =>
    ["completed", "blocked"].includes(item.status),
  );
  const leadStarted = hasEvent(events, ["lead.started", "lead.completed"]);
  const leadCompleted = hasEvent(events, ["lead.completed"]);
  const verificationStarted = hasEvent(events, [
    "verification.started",
    "verification.completed",
  ]);
  const verificationCompleted = hasEvent(events, ["verification.completed"]);
  const leaseReleased = hasEvent(events, ["run.lease_released"]);
  const terminal = [
    "completed",
    "failed",
    "timeout",
    "cancelled",
    "blocked",
  ].includes(run.status);
  return [
    stage(
      "goal",
      "目标",
      localizedGoal(run.goal),
      run.started_at || terminal
        ? terminal
          ? terminalStageStatus(run.status)
          : "running"
        : "not_started",
    ),
    stage(
      "route",
      "能力路由",
      `按数据能力启动 ${run.requested_paths.length} 条路径`,
      pathViews.some((item) => item.status !== "not_started")
        ? "completed"
        : run.phase === "planning"
          ? "running"
          : "not_started",
    ),
    {
      ...stage(
        "fanout",
        "并行路径",
        `${pathViews.length} 条请求路径共享同一调查阶段`,
        pathGroupStatus(pathViews),
      ),
      kind: "fanout",
      paths: pathViews,
    },
    {
      ...stage(
        "barrier",
        "证据屏障",
        leadStarted && allPathsTerminal
          ? `${pathViews.reduce((sum, item) => sum + evidenceCount(item.evidenceCountLabel), 0)} 条证据已持久化，允许综合`
          : "等待请求路径进入终态并持久化结果",
        leadStarted && allPathsTerminal
          ? "completed"
          : pathViews.some((item) => item.status === "blocked")
            ? "blocked"
            : pathViews.some((item) => item.status === "running")
              ? "running"
              : "not_started",
      ),
      derivationLabel:
        leadStarted && allPathsTerminal
          ? "由全部路径终态与主智能体启动事件确认"
          : null,
    },
    stage(
      "lead",
      "主智能体综合",
      leadCompleted
        ? leadDescription(events)
        : leadStarted
          ? "主智能体已开始读取持久化证据"
          : "尚未开始综合",
      leadCompleted ? "completed" : leadStarted ? "running" : "not_started",
    ),
    stage(
      "verification",
      "新鲜上下文验证",
      verificationCompleted
        ? "独立验证通过"
        : verificationStarted
          ? "独立验证进行中"
          : "尚未开始独立验证",
      verificationCompleted
        ? "completed"
        : verificationStarted
          ? "running"
          : "not_started",
    ),
    stage(
      "stop",
      "停止",
      terminal
        ? leaseReleased
          ? `${stopReasonLabel(run.stop_reason ?? run.status)}，资源已释放`
          : `${stopReasonLabel(run.stop_reason ?? run.status)}，资源释放状态未观察`
        : "运行尚未停止",
      terminal ? terminalStageStatus(run.status) : "not_started",
    ),
  ];
}

function buildGenericRunStages(
  run: CommerceRun,
  events: CommerceDomainEvent[],
): CommerceRunStageViewModel[] {
  const terminal = [
    "completed",
    "failed",
    "timeout",
    "cancelled",
    "blocked",
  ].includes(run.status);
  return [
    stage(
      "goal",
      "目标",
      localizedGoal(run.goal),
      run.started_at
        ? terminal
          ? terminalStageStatus(run.status)
          : "running"
        : "not_started",
    ),
    stage(
      "execution",
      runTypeLabel(run.run_type),
      `当前阶段：${runPhaseLabel(run.phase)}`,
      terminal ? terminalStageStatus(run.status) : runStatusToStage(run.status),
    ),
    stage(
      "stop",
      "停止",
      terminal
        ? hasEvent(events, ["run.lease_released"])
          ? `${stopReasonLabel(run.stop_reason ?? run.status)}，资源已释放`
          : `${stopReasonLabel(run.stop_reason ?? run.status)}，资源释放状态未观察`
        : "运行尚未停止",
      terminal ? terminalStageStatus(run.status) : "not_started",
    ),
  ];
}

function stage(
  key: string,
  title: string,
  description: string,
  status: CommerceRunStageStatus,
): CommerceRunStageViewModel {
  return {
    key,
    title,
    description,
    status,
    statusLabel: stageStatusLabel(status),
    kind: "step",
    paths: [],
    derivationLabel: null,
  };
}

function projectPath(
  pathType: string,
  events: CommerceDomainEvent[],
): CommerceRunPathViewModel {
  const completed = findPathEvent(events, "path.completed", pathType);
  const blocked = findPathEvent(events, "path.blocked", pathType);
  const started = findPathEvent(events, "path.started", pathType);
  const status: CommerceRunStageStatus = completed
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
    pathType,
    label: pathLabel(pathType),
    status,
    statusLabel: stageStatusLabel(status),
    evidenceCountLabel:
      completed && evidenceIds.length > 0
        ? `${evidenceIds.length} 条证据`
        : completed
          ? "证据数量未观察"
          : "尚无证据",
  };
}

function findPathEvent(
  events: CommerceDomainEvent[],
  eventType: string,
  pathType: string,
) {
  return events.find(
    (event) =>
      event.event_type === eventType && event.payload.path_type === pathType,
  );
}

function pathGroupStatus(
  paths: CommerceRunPathViewModel[],
): CommerceRunStageStatus {
  if (paths.length === 0) return "not_started";
  if (paths.every((item) => item.status === "completed")) return "completed";
  if (paths.some((item) => item.status === "blocked")) return "blocked";
  if (paths.some((item) => item.status === "running")) return "running";
  return "not_started";
}

function aggregateTelemetry(events: CommerceDomainEvent[]) {
  const modelIdentities = new Set<string>();
  const requestIds = new Set<string>();
  const stopReasons = new Set<string>();
  let tokens = 0;
  let latencyMs = 0;
  let retries = 0;
  let tokenObserved = false;
  let latencyObserved = false;
  let retryObserved = false;
  for (const event of events) {
    const payload = event.payload;
    if (typeof payload.actual_model_identity === "string") {
      modelIdentities.add(payload.actual_model_identity);
    }
    if (typeof payload.provider_request_id === "string") {
      requestIds.add(payload.provider_request_id);
    }
    if (Array.isArray(payload.provider_request_ids)) {
      for (const value of payload.provider_request_ids) {
        if (typeof value === "string") requestIds.add(value);
      }
    }
    if (typeof payload.total_tokens === "number") {
      tokens += payload.total_tokens;
      tokenObserved = true;
    }
    if (typeof payload.latency_ms === "number") {
      latencyMs += payload.latency_ms;
      latencyObserved = true;
    }
    if (typeof payload.retry_count === "number") {
      retries += payload.retry_count;
      retryObserved = true;
    }
    if (typeof payload.stop_reason === "string") {
      stopReasons.add(payload.stop_reason);
    }
  }
  return {
    modelIdentityLabel:
      modelIdentities.size === 0
        ? "未观察"
        : modelIdentities.size === 1
          ? [...modelIdentities][0]!
          : `${modelIdentities.size} 个模型身份`,
    requestCountLabel:
      requestIds.size === 0 ? "未观察" : `${requestIds.size} 个唯一 ID`,
    tokenLabel: tokenObserved ? formatInteger(tokens) : "未观察",
    latencyLabel: latencyObserved ? formatDurationMs(latencyMs) : "未观察",
    retryLabel: retryObserved ? formatInteger(retries) : "未观察",
    stopReasonLabel:
      stopReasons.size === 0
        ? "未观察"
        : stopReasons.size === 1
          ? [...stopReasons][0]!
          : `${stopReasons.size} 种停止原因`,
  };
}

function projectBudget(checkpoint: CommerceRunCheckpoint) {
  const { limit, usage } = checkpoint.checkpoint.budget_snapshot;
  return [
    budgetRow("循环", usage.iterations, limit.max_iterations),
    budgetRow("工具", usage.tool_calls, limit.max_tool_calls),
    budgetRow("路径", usage.path_agents, limit.max_path_agents),
    budgetRow("令牌", usage.tokens, limit.max_tokens),
  ];
}

function budgetRow(label: string, used: number, limit: number) {
  return {
    label,
    valueLabel: `${formatInteger(used)} / ${formatInteger(limit)}`,
    ratio: limit <= 0 ? 0 : Math.min(1, used / limit),
  };
}

function sortRunEvents(events: CommerceDomainEvent[]) {
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

function hasEvent(events: CommerceDomainEvent[], types: string[]): boolean {
  return events.some((item) => types.includes(item.event_type));
}

function leadDescription(events: CommerceDomainEvent[]): string {
  const completed = events.find((item) => item.event_type === "lead.completed");
  const count = completed?.payload.claim_count;
  return typeof count === "number"
    ? `形成 ${count} 个工作假设`
    : "主智能体综合已完成";
}

function evidenceCount(label: string): number {
  const match = /^(\d+) 条证据$/u.exec(label);
  return match ? Number(match[1]) : 0;
}

function runStatusGroup(status: string): Exclude<CommerceRunFilter, "all"> {
  if (status === "running" || status === "queued") return "running";
  if (status === "waiting") return "waiting";
  if (status === "completed") return "completed";
  return "failed";
}

function runStatusLabel(status: string): string {
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

function runTypeLabel(type: string): string {
  return (
    {
      data_intake: "数据接入",
      case_investigation: "案例调查",
      action_execution: "行动执行",
      follow_up: "行动跟踪",
      replan: "重新规划",
      evaluation: "离线评测",
    }[type] ?? "运行类型待确认"
  );
}

function runPhaseLabel(phase: string): string {
  return (
    {
      profiling: "数据画像",
      mapping: "字段映射",
      planning: "规划",
      investigating: "调查",
      synthesizing: "综合",
      verifying: "验证",
      validating_action: "行动校验",
      awaiting_approval: "等待审批",
      executing: "执行",
      evaluating_follow_up: "跟踪评估",
    }[phase] ?? "阶段待确认"
  );
}

function localizedRunTitle(run: CommerceRun): string {
  if (/\p{Script=Han}/u.test(run.goal)) return run.goal;
  const normalized = run.goal.toLowerCase();
  if (run.run_type === "replan") return "重新规划调查路径";
  if (run.run_type === "action_execution") {
    return run.action_operation === "rollback" ? "回滚行动" : "执行候选行动";
  }
  if (run.run_type === "follow_up") return "评估行动后续结果";
  if (normalized.includes("review")) return "调查评价体验问题";
  if (normalized.includes("peer")) return "调查卖家对标差异";
  if (normalized.includes("delivery") || normalized.includes("fulfillment")) {
    return "调查履约延迟原因";
  }
  return "检查经营诊断运行";
}

function localizedGoal(goal: string): string {
  if (/\p{Script=Han}/u.test(goal)) return goal;
  const normalized = goal.toLowerCase();
  if (normalized.includes("delivery") || normalized.includes("fulfillment")) {
    return "解释履约延迟异常并形成可追溯结论";
  }
  if (normalized.includes("review")) return "解释评价体验异常并形成可追溯结论";
  if (normalized.includes("peer")) return "解释卖家对标差异并形成可追溯结论";
  return "完成当前经营诊断目标";
}

function localizedCaseTitle(item: CommerceCase | undefined): string {
  if (!item) return "案例标题不可用";
  if (/\p{Script=Han}/u.test(item.title)) return item.title;
  const source = `${item.title} ${item.summary ?? ""}`.toLowerCase();
  if (source.includes("review") || /评价|评分/u.test(source))
    return "评价体验异常";
  if (source.includes("peer") || /卖家|对标/u.test(source))
    return "卖家对标异常";
  if (
    source.includes("delivery") ||
    source.includes("fulfillment") ||
    /履约|承运/u.test(source)
  ) {
    return "履约延迟异常";
  }
  return "经营诊断案例";
}

function stopReasonLabel(reason: string): string {
  return (
    {
      goal_achieved: "目标已满足",
      goal_partially_achieved: "目标部分满足",
      awaiting_user_input: "等待用户输入",
      awaiting_approval: "等待审批",
      capability_blocked: "数据能力阻塞",
      budget_exceeded: "预算已耗尽",
      no_new_evidence: "没有新增证据",
      verification_replan_required: "验证要求重新规划",
      policy_blocked: "策略阻止",
      tool_failure: "工具失败",
      cancelled: "已取消",
      completed: "运行已完成",
      failed: "运行失败",
      timeout: "运行超时",
      blocked: "运行阻塞",
    }[reason] ?? reason
  );
}

function waitReasonLabel(reason: string): string {
  return (
    {
      awaiting_user_input: "等待用户输入",
      awaiting_approval: "等待审批",
    }[reason] ?? reason
  );
}

function pathLabel(pathType: string): string {
  return (
    {
      fulfillment: "履约路径",
      seller_peer: "卖家对标",
      review_experience: "评价体验",
    }[pathType] ?? "未知路径"
  );
}

function stageStatusLabel(status: CommerceRunStageStatus): string {
  return {
    completed: "已完成",
    running: "进行中",
    waiting: "等待中",
    blocked: "已阻塞",
    not_started: "未开始",
  }[status];
}

function terminalStageStatus(status: string): CommerceRunStageStatus {
  return status === "completed" ? "completed" : "blocked";
}

function runStatusToStage(status: string): CommerceRunStageStatus {
  if (status === "waiting") return "waiting";
  if (status === "running" || status === "queued") return "running";
  if (status === "completed") return "completed";
  return "blocked";
}

function eventTitle(eventType: string): string {
  return (
    {
      "run.created": "运行已创建",
      "run.checkpoint_saved": "检查点已保存",
      "run.lease_released": "运行资源已释放",
      "path.started": "路径已启动",
      "path.completed": "路径已完成",
      "path.blocked": "路径已阻塞",
      "lead.started": "主智能体综合已启动",
      "lead.completed": "主智能体综合已完成",
      "verification.started": "独立验证已启动",
      "verification.completed": "独立验证已完成",
    }[eventType] ?? `未知事件：${eventType}`
  );
}

function runDurationLabel(run: CommerceRun): string {
  if (!run.started_at || !run.ended_at) return "未观察";
  return formatDurationMs(
    Date.parse(run.ended_at) - Date.parse(run.started_at),
  );
}

function runPeriodLabel(run: CommerceRun): string {
  if (!run.started_at) return `创建于 ${formatTime(run.created_at)}`;
  return run.ended_at
    ? `${formatTime(run.started_at)}—${formatTime(run.ended_at)}`
    : `${formatTime(run.started_at)} 开始`;
}

function formatDurationMs(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "未观察";
  const seconds = value / 1000;
  return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(seconds)} 秒`;
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(
    value,
  );
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function shortId(value: string): string {
  return value.length <= 14 ? value : `${value.slice(0, 4)}…${value.slice(-6)}`;
}
