import type {
  CommerceActionDetail,
  CommerceActionParameters,
  CommerceActionRecord,
  CommerceCase,
} from "./types";

export type CommerceActionFilter =
  | "all"
  | "needs_action"
  | "in_progress"
  | "monitoring"
  | "ended";

export interface CommerceActionQueueItemViewModel {
  id: string;
  caseId: string;
  caseTitle: string;
  title: string;
  statusLabel: string;
  statusGroup: Exclude<CommerceActionFilter, "all">;
  riskLabel: string;
  policyLabel: string;
  approvalLabel: string;
  updatedLabel: string;
}

export interface CommerceActionDetailViewModel extends CommerceActionQueueItemViewModel {
  description: string;
  policyDispositionLabel: string;
  policyDescription: string;
  executionToolLabel: string;
  evidenceSummary: string;
  hypothesisSummary: string;
  planRows: Array<{ label: string; value: string }>;
  rollback: {
    strategy: string;
    trigger: string;
    verification: string;
  };
  approvalProgressLabel: string | null;
  artifactLabel: string | null;
  canExecute: boolean;
  canRollback: boolean;
  canApprove: boolean;
  canReject: boolean;
  primaryActionLabel: string | null;
}

export interface CommerceActionCenterViewModel {
  title: string;
  subtitle: string;
  filters: Array<{
    value: CommerceActionFilter;
    label: string;
    count: number;
  }>;
  items: CommerceActionQueueItemViewModel[];
  selected: CommerceActionDetailViewModel | null;
}

export function buildCommerceActionCenterViewModel({
  cases,
  records,
  selectedActionId,
  selectedDetail,
}: {
  cases: CommerceCase[];
  records: CommerceActionRecord[];
  selectedActionId?: string | null;
  selectedDetail: CommerceActionDetail | null;
}): CommerceActionCenterViewModel {
  const caseMap = new Map(cases.map((item) => [item.id, item]));
  const items = [...records]
    .sort(
      (left, right) =>
        Date.parse(right.updated_at) - Date.parse(left.updated_at),
    )
    .map((record) => projectQueueItem(record, caseMap));
  const activeActionId =
    selectedActionId && items.some((item) => item.id === selectedActionId)
      ? selectedActionId
      : items[0]?.id;
  const activeRecord = records.find(
    (item) => item.action.id === activeActionId,
  );
  const detail =
    selectedDetail?.record.action.id === activeActionId
      ? selectedDetail
      : activeRecord
        ? {
            record: activeRecord,
            approval: null,
            artifact: null,
            follow_ups: [],
          }
        : null;
  return {
    title: "审查与执行行动",
    subtitle: "行动必须有证据、策略判断和回滚方案，执行后再进入跟踪。",
    filters: [
      filterOption("all", "全部", items),
      filterOption("needs_action", "待处理", items),
      filterOption("in_progress", "执行中", items),
      filterOption("monitoring", "跟踪中", items),
      filterOption("ended", "已结束", items),
    ],
    items,
    selected: detail ? projectDetail(detail, caseMap) : null,
  };
}

export function filterCommerceActionItems(
  items: readonly CommerceActionQueueItemViewModel[],
  options: { filter: CommerceActionFilter; query: string },
): CommerceActionQueueItemViewModel[] {
  const query = options.query.trim().toLocaleLowerCase("zh-CN");
  return items.filter((item) => {
    if (options.filter !== "all" && item.statusGroup !== options.filter) {
      return false;
    }
    if (!query) return true;
    return [item.title, item.caseTitle, item.statusLabel, item.riskLabel]
      .join(" ")
      .toLocaleLowerCase("zh-CN")
      .includes(query);
  });
}

function filterOption(
  value: CommerceActionFilter,
  label: string,
  items: readonly CommerceActionQueueItemViewModel[],
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

function projectQueueItem(
  record: CommerceActionRecord,
  cases: Map<string, CommerceCase>,
): CommerceActionQueueItemViewModel {
  const action = record.action;
  return {
    id: action.id,
    caseId: action.case_id,
    caseTitle: localizedCaseTitle(cases.get(action.case_id)),
    title: actionTitle(record),
    statusLabel: actionStatusLabel(action.status),
    statusGroup: actionStatusGroup(action.status),
    riskLabel: riskLabel(action.risk_level),
    policyLabel: `策略 ${record.decision.level}`,
    approvalLabel: approvalLabel(record),
    updatedLabel: formatTime(record.updated_at),
  };
}

function projectDetail(
  detail: CommerceActionDetail,
  cases: Map<string, CommerceCase>,
): CommerceActionDetailViewModel {
  const record = detail.record;
  const base = projectQueueItem(record, cases);
  const action = record.action;
  const draft = record.decision.validated.draft;
  const approval = detail.approval;
  const approvalApproved =
    !action.approval.required ||
    action.approval.status === "approved" ||
    approval?.status === "approved";
  const canExecute =
    ["policy_checked", "approved"].includes(action.status) &&
    record.decision.disposition !== "blocked" &&
    approvalApproved;
  const canRollback = ["succeeded", "monitoring"].includes(action.status);
  const canApprove = approval?.status === "pending";
  const canReject = approval?.status === "pending";
  return {
    ...base,
    description: actionDescription(record),
    policyDispositionLabel: policyDispositionLabel(record.decision.disposition),
    policyDescription: policyDescription(record),
    executionToolLabel: record.decision.execution_tool ?? "没有可执行工具",
    evidenceSummary: `引用 ${draft.evidence_ids.length} 条证据和 ${draft.hypothesis_ids.length} 个工作假设`,
    hypothesisSummary:
      draft.hypothesis_ids.length > 0
        ? "行动引用已验证的工作假设，但不能单独证明因果关系。"
        : "当前行动没有可追溯的工作假设。",
    planRows: actionPlanRows(draft.parameters),
    rollback: {
      strategy: action.rollback_plan.strategy,
      trigger: action.rollback_plan.trigger,
      verification: action.rollback_plan.verification,
    },
    approvalProgressLabel: approval
      ? `已批准 ${approval.approved_actor_ids.length} / ${approval.required_approvals}`
      : null,
    artifactLabel: detail.artifact
      ? `${artifactKindLabel(detail.artifact.payload.kind)} · ${artifactStatusLabel(detail.artifact.status)}`
      : null,
    canExecute,
    canRollback,
    canApprove,
    canReject,
    primaryActionLabel: canApprove
      ? "批准行动"
      : canExecute
        ? "执行行动"
        : canRollback
          ? "回滚行动"
          : null,
  };
}

function actionTitle(record: CommerceActionRecord): string {
  const parameters = record.decision.validated.draft.parameters;
  if (/\p{Script=Han}/u.test(record.action.title)) return record.action.title;
  switch (parameters.kind) {
    case "create_metric_monitor":
      return `创建${metricLabel(parameters.metric_name)}跟踪`;
    case "request_missing_data":
      return "请求补充缺失经营数据";
    case "export_audit_cohort":
      return "导出问题订单审计清单";
    case "create_internal_task":
      return "创建内部复核任务";
    case "no_op":
      return "保留当前结论，不执行操作";
    case "external_mutation":
      return "受策略约束的外部操作";
  }
}

function actionDescription(record: CommerceActionRecord): string {
  const parameters = record.decision.validated.draft.parameters;
  if (/\p{Script=Han}/u.test(record.action.description)) {
    return record.action.description;
  }
  switch (parameters.kind) {
    case "create_metric_monitor":
      return `每 ${parameters.cadence_hours} 小时检查一次${metricLabel(parameters.metric_name)}，并在 ${parameters.follow_up_after_days} 天后重新评估当前案例。`;
    case "request_missing_data":
      return `请求补充 ${parameters.missing_fields.length} 个缺失字段，并在 ${parameters.due_days} 天内完成。`;
    case "export_audit_cohort":
      return `导出最多 ${parameters.max_rows} 行的可审计问题清单，不包含直接身份信息。`;
    case "create_internal_task":
      return `为${parameters.owner_role}创建内部复核任务，截止时间为 ${parameters.due_days} 天后。`;
    case "no_op":
      return "当前只保留结论和审计记录，不创建写操作。";
    case "external_mutation":
      return "该外部操作只能在服务端策略和审批门禁全部通过后执行。";
  }
}

function actionPlanRows(
  parameters: CommerceActionParameters,
): Array<{ label: string; value: string }> {
  switch (parameters.kind) {
    case "create_metric_monitor":
      return [
        { label: "行动类型", value: "指标跟踪" },
        { label: "监控指标", value: metricLabel(parameters.metric_name) },
        {
          label: "判断条件",
          value: `${comparisonLabel(parameters.comparison)} ${formatThreshold(parameters.metric_name, parameters.threshold)}`,
        },
        { label: "检查频率", value: `每 ${parameters.cadence_hours} 小时` },
        { label: "复评时间", value: `${parameters.follow_up_after_days} 天后` },
      ];
    case "request_missing_data":
      return [
        { label: "行动类型", value: "请求补充数据" },
        { label: "缺失字段", value: parameters.missing_fields.join("、") },
        { label: "截止时间", value: `${parameters.due_days} 天后` },
      ];
    case "export_audit_cohort":
      return [
        { label: "行动类型", value: "导出审计清单" },
        { label: "文件格式", value: parameters.format.toUpperCase() },
        { label: "最大行数", value: `${parameters.max_rows} 行` },
        { label: "直接身份信息", value: "不包含" },
      ];
    case "create_internal_task":
      return [
        { label: "行动类型", value: "内部复核任务" },
        { label: "负责角色", value: parameters.owner_role },
        { label: "截止时间", value: `${parameters.due_days} 天后` },
        { label: "检查项", value: parameters.checklist.join("、") },
      ];
    case "no_op":
      return [
        { label: "行动类型", value: "仅记录" },
        { label: "原因", value: parameters.reason },
      ];
    case "external_mutation":
      return [
        { label: "行动类型", value: "外部受控操作" },
        { label: "连接器", value: parameters.connector_id },
        { label: "操作", value: parameters.operation },
        { label: "试运行", value: parameters.dry_run ? "是" : "否" },
        { label: "可回滚", value: parameters.reversible ? "是" : "否" },
      ];
  }
}

function actionStatusGroup(
  status: CommerceActionRecord["action"]["status"],
): Exclude<CommerceActionFilter, "all"> {
  if (["executing", "rolling_back"].includes(status)) return "in_progress";
  if (status === "monitoring") return "monitoring";
  if (
    ["policy_checked", "awaiting_approval", "approved", "failed"].includes(
      status,
    )
  ) {
    return "needs_action";
  }
  return "ended";
}

function actionStatusLabel(
  status: CommerceActionRecord["action"]["status"],
): string {
  const labels: Record<typeof status, string> = {
    draft: "草稿",
    validating: "正在校验",
    policy_checked: "待执行",
    awaiting_approval: "等待审批",
    approved: "已批准",
    rejected: "已拒绝",
    executing: "执行中",
    succeeded: "已完成",
    failed: "执行失败",
    monitoring: "跟踪中",
    effective: "跟踪有效",
    ineffective: "跟踪无效",
    inconclusive: "结论不足",
    rolling_back: "回滚中",
    rolled_back: "已回滚",
  };
  return labels[status];
}

function riskLabel(risk: CommerceActionRecord["action"]["risk_level"]): string {
  return {
    low: "低风险",
    medium: "中风险",
    high: "高风险",
    critical: "严重风险",
  }[risk];
}

function approvalLabel(record: CommerceActionRecord): string {
  const approval = record.action.approval;
  if (!approval.required) return "无需审批";
  return {
    pending: "等待审批",
    approved: "审批通过",
    rejected: "审批拒绝",
    expired: "审批过期",
    revoked: "原审批已撤销",
    not_required: "无需审批",
  }[approval.status];
}

function policyDispositionLabel(
  disposition: CommerceActionRecord["decision"]["disposition"],
): string {
  return {
    auto_execute: "允许执行",
    approval_required: "审批后可执行",
    blocked: "策略已阻止",
  }[disposition];
}

function policyDescription(record: CommerceActionRecord): string {
  if (record.decision.disposition === "auto_execute") {
    return "内部可逆操作，无需人工审批。";
  }
  if (record.decision.disposition === "approval_required") {
    return `需要 ${record.decision.required_approvals} 人审批后才能执行。`;
  }
  return "当前连接器、风险或不可逆约束不允许执行。";
}

function comparisonLabel(
  value: "less_than_or_equal" | "greater_than_or_equal",
) {
  return value === "less_than_or_equal" ? "小于或等于" : "大于或等于";
}

function formatThreshold(metricName: string, raw: string): string {
  const value = Number(raw);
  if (
    Number.isFinite(value) &&
    metricName.includes("rate") &&
    Math.abs(value) <= 1
  ) {
    return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value * 100)}%`;
  }
  return raw;
}

function metricLabel(name: string): string {
  const labels: Readonly<Record<string, string>> = {
    late_delivery_rate: "延迟履约率",
    review_score: "评价得分",
    negative_review_rate: "负面评价率",
    handling_time_hours: "平均处理时长",
  };
  return labels[name] ?? name;
}

function localizedCaseTitle(item: CommerceCase | undefined): string {
  if (!item) return "案例标题不可用";
  if (/\p{Script=Han}/u.test(item.title)) return item.title;
  const summary = item.summary ?? "";
  if (/延迟履约|履约延迟|承运/u.test(summary)) return "履约延迟异常";
  if (/评价|评分|商品体验/u.test(summary)) return "评价体验异常";
  if (/卖家|对标|同类/u.test(summary)) return "卖家对标诊断";
  return "经营诊断案例";
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function artifactKindLabel(kind: string): string {
  return (
    {
      no_op_receipt: "只读回执",
      audit_export: "审计清单",
      internal_task: "内部任务",
      metric_monitor: "指标跟踪",
      data_request: "数据请求",
    }[kind] ?? "执行产物"
  );
}

function artifactStatusLabel(status: string): string {
  return (
    {
      completed: "已完成",
      available: "可用",
      open: "进行中",
      active: "已启用",
      cancelled: "已取消",
      disabled: "已停用",
      archived: "已归档",
    }[status] ?? "状态待确认"
  );
}
