import {
  buildCommerceEvidenceExplorerViewModel,
  type CommerceEvidenceExplorerViewModel,
} from "./evidence-explorer-view-model";
import {
  type CommerceCase,
  type CommerceCaseActionSummary,
  type CommerceCaseAnomaly,
  type CommerceCaseDetail,
  type CommerceDomainEvent,
  type CommerceEvidence,
  type CommerceHypothesis,
  type CommerceMetricObservation,
  type CommerceRun,
  type CommerceWorkspaceSnapshot,
} from "./types";

const CHINESE_TEXT = /[\u3400-\u9fff]/u;

const PATH_LABELS: Readonly<Record<string, string>> = {
  fulfillment: "履约分析",
  review_experience: "评价体验",
  seller_peer: "卖家对标",
};

const SEVERITY_LABELS: Readonly<Record<string, string>> = {
  critical: "紧急",
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

const CASE_STATUS_LABELS: Readonly<Record<string, string>> = {
  new: "待调查",
  triaged: "已分诊",
  investigating: "调查中",
  awaiting_data: "等待数据",
  awaiting_approval: "等待审批",
  action_in_progress: "行动执行中",
  monitoring: "跟踪中",
  blocked: "已阻塞",
  resolved: "已解决",
  reopened: "已重新打开",
  inconclusive: "结论不足",
  cancelled: "已取消",
};

const METRIC_LABELS: Readonly<Record<string, string>> = {
  order_count: "订单量",
  late_delivery_rate: "延迟履约率",
  handling_time_hours: "平均处理时长",
  transit_time_hours: "平均运输时长",
  delivery_duration_hours: "平均履约时长",
  average_review_score: "平均评价得分",
  low_rating_rate: "低分评价率",
  peer_late_delivery_rate: "同类卖家延迟履约率",
  geographic_order_count: "区域订单量",
};

export interface CommerceNavigationCaseViewModel {
  id: string;
  title: string;
  severityLabel: string;
  statusLabel: string;
  isActive: boolean;
}

export interface CommerceTimelineItemViewModel {
  id: string;
  kind: "known" | "unknown";
  title: string;
  description: string;
  timeLabel: string;
  state: "neutral" | "running" | "completed" | "blocked";
}

export interface CommerceEvidenceViewModel {
  id: string;
  typeLabel: string;
  summary: string;
  statusLabel: string;
  relation: "supports" | "contradicts" | "unknown";
}

export interface CommerceSubagentViewModel {
  pathType: string;
  label: string;
  status: "waiting" | "running" | "completed" | "blocked";
  statusLabel: string;
}

export interface CommerceMetricComparisonViewModel {
  metricName: string;
  metricLabel: string;
  baselineMetricId: string;
  currentMetricId: string;
  baselineValueLabel: string;
  currentValueLabel: string;
  changeLabel: string;
  direction: "increase" | "decrease" | "unknown";
}

export interface CommerceEvidenceInspectorViewModel {
  evidenceId: string;
  title: string;
  statusLabel: string;
  typeLabel: string;
  relationLabel: string;
  periodLabel: string;
  baselineValueLabel: string;
  currentValueLabel: string;
  changeLabel: string;
  sourceLabel: string;
  formulaLabel: string;
  lineageLabel: string;
}

export interface CommerceCaseOverviewViewModel {
  periodLabel: string;
  updatedLabel: string;
  evidenceCountLabel: string;
  problemStatement: string;
  comparison: CommerceMetricComparisonViewModel | null;
  conclusion: {
    description: string;
    verificationLabel: string;
    verified: boolean;
  };
  evidenceBoundary: {
    verifiedCount: number;
    supportingCount: number;
    contradictingCount: number;
    summary: string;
    unknownSummary: string;
    primaryEvidenceId: string | null;
  };
  action: {
    id: string | null;
    title: string;
    statusLabel: string;
    available: boolean;
  };
  evidenceInspector: CommerceEvidenceInspectorViewModel | null;
  analysisUnavailableLabel: string | null;
}

export interface CommerceShellViewModel {
  status: "empty" | "ready";
  navigation: {
    cases: CommerceNavigationCaseViewModel[];
  };
  activeCase: null | {
    id: string;
    title: string;
    sellerLabel: string;
    subtitle: string;
    severityLabel: string;
    statusLabel: string;
    pathLabel: string;
    evidence: CommerceEvidenceViewModel[];
    evidenceExplorer: CommerceEvidenceExplorerViewModel;
    overview: CommerceCaseOverviewViewModel;
    hypothesisState: {
      label: string;
      description: string;
    };
    actionState: {
      label: string;
      description: string;
      available: boolean;
    };
  };
  timeline: {
    items: CommerceTimelineItemViewModel[];
    wasReordered: boolean;
  };
  subagents: CommerceSubagentViewModel[];
  evidenceSources: Array<{ label: string; count: number }>;
  runtime: {
    modelLabel: string;
    retryLabel: string;
    leaseLabel: string;
    stateLabel: string;
  };
  emptyState: null | {
    title: string;
    description: string;
    actionLabel: string;
  };
}

export function buildCommerceShellViewModel(
  snapshot: CommerceWorkspaceSnapshot,
): CommerceShellViewModel {
  if (!snapshot.selectedCase) {
    return {
      status: "empty",
      navigation: {
        cases: snapshot.cases.map((item) => navigationCase(item, null)),
      },
      activeCase: null,
      timeline: { items: [], wasReordered: false },
      subagents: [],
      evidenceSources: [],
      runtime: {
        modelLabel: "尚无模型调用",
        retryLabel: "暂无重试记录",
        leaseLabel: "当前无租约",
        stateLabel: "当前没有运行中的调查",
      },
      emptyState: {
        title: "还没有经营案例",
        description:
          "接入电商数据后，系统会先检查数据能力，再创建可追溯的诊断案例。",
        actionLabel: "接入数据",
      },
    };
  }

  const {
    case: selectedCase,
    lineage,
    evidence,
    hypotheses,
    analysis,
    actions,
  } = snapshot.selectedCase;
  const orderedEvents = orderEvents(snapshot.events);
  const primaryPath = inferPrimaryPath(orderedEvents.items);
  const sellerSuffix = lineage?.seller_external_key.slice(-4);
  const evidenceView = evidence.map(projectEvidence);
  const latestRun = latestByUpdatedAt(snapshot.runs);
  const overview = projectCaseOverview({
    selectedCase,
    lineage,
    evidence,
    hypotheses,
    analysis,
    actions,
    events: orderedEvents.items,
    primaryPath,
  });
  const topicLabel = caseTopicLabel(
    selectedCase,
    primaryPath,
    overview.comparison?.metricName ??
      analysis.current_metrics[0]?.metric_name ??
      analysis.baseline_metrics[0]?.metric_name ??
      null,
    analysis.anomalies.length > 0,
  );

  return {
    status: "ready",
    navigation: {
      cases: snapshot.cases.map((item) =>
        navigationCase(
          item,
          selectedCase.id,
          item.id === selectedCase.id ? topicLabel : undefined,
        ),
      ),
    },
    activeCase: {
      id: selectedCase.id,
      title: topicLabel,
      sellerLabel: sellerSuffix ? `卖家 ${sellerSuffix}` : "当前经营主体",
      subtitle: buildCaseSubtitle(
        sellerSuffix,
        evidence.length,
        overview.comparison,
      ),
      severityLabel: labelFromMap(
        SEVERITY_LABELS,
        selectedCase.severity,
        "待分级",
      ),
      statusLabel: labelFromMap(
        CASE_STATUS_LABELS,
        selectedCase.status,
        "状态待确认",
      ),
      pathLabel: primaryPath
        ? `${pathLabel(primaryPath)}路径`
        : "能力路由待确认",
      evidence: evidenceView,
      evidenceExplorer: buildCommerceEvidenceExplorerViewModel(
        snapshot.selectedCase,
      ),
      overview,
      hypothesisState: projectHypothesisState(hypotheses),
      actionState: overview.action.available
        ? {
            label: overview.action.title,
            description: overview.action.statusLabel,
            available: true,
          }
        : {
            label: "尚无候选行动",
            description: overview.action.statusLabel,
            available: false,
          },
    },
    timeline: {
      items: orderedEvents.items.map(projectTimelineItem),
      wasReordered: orderedEvents.wasReordered,
    },
    subagents: projectSubagents(orderedEvents.items, latestRun),
    evidenceSources: projectEvidenceSources(evidence),
    runtime: projectRuntime(orderedEvents.items, latestRun),
    emptyState: null,
  };
}

function navigationCase(
  item: CommerceCase,
  activeCaseId: string | null,
  resolvedTitle?: string,
): CommerceNavigationCaseViewModel {
  return {
    id: item.id,
    title: resolvedTitle ?? localizedCaseTitle(item.title),
    severityLabel: labelFromMap(SEVERITY_LABELS, item.severity, "待分级"),
    statusLabel: labelFromMap(CASE_STATUS_LABELS, item.status, "状态待确认"),
    isActive: item.id === activeCaseId,
  };
}

function localizedCaseTitle(title: string): string {
  if (CHINESE_TEXT.test(title)) return title;
  const normalized = title.toLowerCase();
  if (normalized.includes("review")) return "评价体验异常";
  if (normalized.includes("delivery") || normalized.includes("fulfillment")) {
    return "履约延迟异常";
  }
  if (normalized.includes("peer")) return "卖家对标异常";
  if (normalized.includes("user-requested")) return "用户发起的经营诊断";
  if (normalized.includes("deterministic anomaly")) {
    return "系统检测到的经营异常";
  }
  return "经营异常案例";
}

function caseTopicLabel(
  selectedCase: CommerceCase,
  primaryPath: string | null,
  primaryMetricName: string | null,
  hasAnomaly: boolean,
) {
  const explicitUserRequest = selectedCase.title
    .toLocaleLowerCase("en-US")
    .includes("user-requested");
  if (explicitUserRequest && !hasAnomaly) {
    if (
      primaryPath === "fulfillment" ||
      (primaryMetricName &&
        [
          "late_delivery_rate",
          "handling_time_hours",
          "transit_time_hours",
          "delivery_duration_hours",
        ].includes(primaryMetricName))
    ) {
      return "用户发起的履约诊断";
    }
    if (
      primaryPath === "review_experience" ||
      (primaryMetricName &&
        ["average_review_score", "low_rating_rate"].includes(primaryMetricName))
    ) {
      return "用户发起的评价诊断";
    }
    if (
      primaryPath === "seller_peer" ||
      primaryMetricName?.startsWith("peer_")
    ) {
      return "用户发起的卖家对标";
    }
    return "用户发起的经营诊断";
  }
  if (primaryPath === "fulfillment") return "履约延迟异常";
  if (primaryPath === "review_experience") return "评价体验异常";
  if (primaryPath === "seller_peer") return "卖家对标异常";
  if (
    primaryMetricName &&
    [
      "late_delivery_rate",
      "handling_time_hours",
      "transit_time_hours",
      "delivery_duration_hours",
    ].includes(primaryMetricName)
  ) {
    return "履约延迟异常";
  }
  if (
    primaryMetricName &&
    ["average_review_score", "low_rating_rate"].includes(primaryMetricName)
  ) {
    return "评价体验异常";
  }
  if (primaryMetricName?.startsWith("peer_")) return "卖家对标异常";
  const localized = localizedCaseTitle(selectedCase.title);
  return localized.endsWith("诊断") ? localized.slice(0, -2) : localized;
}

function buildCaseSubtitle(
  sellerSuffix: string | undefined,
  evidenceCount: number,
  comparison: CommerceMetricComparisonViewModel | null,
): string {
  const subject = sellerSuffix ? `卖家 ${sellerSuffix}` : "当前经营主体";
  if (comparison) {
    const directionLabel =
      comparison.direction === "increase"
        ? "显著上升"
        : comparison.direction === "decrease"
          ? "显著下降"
          : "发生显著变化";
    return `${subject} 当前周期的${comparison.metricLabel}${directionLabel}`;
  }
  if (evidenceCount === 0) {
    return `${subject} 的调查已创建，正在等待可核验的证据。`;
  }
  return `${subject} 已收集 ${evidenceCount} 条可追溯证据，正在评估下一步行动。`;
}

function projectCaseOverview({
  selectedCase,
  lineage,
  evidence,
  hypotheses,
  analysis,
  actions,
  events,
  primaryPath,
}: {
  selectedCase: CommerceCase;
  lineage: CommerceCaseDetail["lineage"];
  evidence: CommerceEvidence[];
  hypotheses: CommerceHypothesis[];
  analysis: CommerceCaseDetail["analysis"];
  actions: CommerceCaseActionSummary[];
  events: CommerceDomainEvent[];
  primaryPath: string | null;
}): CommerceCaseOverviewViewModel {
  const comparison = projectMetricComparison(
    analysis.anomalies,
    analysis.baseline_metrics,
    analysis.current_metrics,
  );
  const verifiedCount = evidence.filter(
    (item) => !["unknown", "blocked"].includes(item.semantic_status),
  ).length;
  const supportingCount = evidence.filter(
    (item) => item.relation === "supports",
  ).length;
  const contradictingCount = evidence.filter(
    (item) => item.relation === "contradicts",
  ).length;
  const primaryEvidence = selectPrimaryEvidence(evidence, comparison);
  const latestHypothesis = [...hypotheses].sort(
    (left, right) => right.version - left.version,
  )[0];
  const verification = [...events]
    .reverse()
    .find((item) => item.event_type === "verification.completed");
  const verdict = verification
    ? payloadString(verification, "overall_verdict")
    : null;
  const verified = verification !== undefined && verdict !== "failed";
  const analysisUnavailableLabel =
    analysis.status === "unavailable"
      ? analysisUnavailableReasonLabel(analysis.unavailable_reason)
      : null;
  const action = projectOverviewAction(actions, primaryPath);
  const periodLabel = lineage
    ? formatAnalysisPeriod(lineage.current_start, lineage.current_end)
    : "分析周期不可用";

  return {
    periodLabel,
    updatedLabel: formatUpdatedTime(selectedCase.updated_at),
    evidenceCountLabel: `${evidence.length} 条证据`,
    problemStatement: comparison
      ? `${comparison.metricLabel}从 ${comparison.baselineValueLabel} 变为 ${comparison.currentValueLabel}，需要继续判断异常来自经营结构、过程时长还是外部履约表现。`
      : (analysisUnavailableLabel ?? "当前没有可复算的异常指标对比。"),
    comparison,
    conclusion: {
      description: conclusionDescription(primaryPath, latestHypothesis),
      verificationLabel: verificationLabel(verification !== undefined, verdict),
      verified,
    },
    evidenceBoundary: {
      verifiedCount,
      supportingCount,
      contradictingCount,
      summary:
        verifiedCount > 0
          ? `${verifiedCount} 条证据已核验，${supportingCount} 条支持当前判断`
          : "当前还没有完成核验的证据",
      unknownSummary:
        analysisUnavailableLabel ??
        (latestHypothesis?.status === "supported"
          ? "仍需补充外部记录或可靠对照，才能判断因果关系"
          : "工作假设和未知项仍需要继续核验"),
      primaryEvidenceId: primaryEvidence?.id ?? null,
    },
    action,
    evidenceInspector: primaryEvidence
      ? projectEvidenceInspector({
          evidence: primaryEvidence,
          comparison,
          periodLabel,
          analysisAvailable: analysis.status === "available",
        })
      : null,
    analysisUnavailableLabel,
  };
}

function projectMetricComparison(
  anomalies: CommerceCaseAnomaly[],
  baselineMetrics: CommerceMetricObservation[],
  currentMetrics: CommerceMetricObservation[],
): CommerceMetricComparisonViewModel | null {
  const priority = [
    "late_delivery_rate",
    "average_review_score",
    "low_rating_rate",
    "delivery_duration_hours",
    "handling_time_hours",
    "transit_time_hours",
    "peer_late_delivery_rate",
  ];
  const anomaly = [...anomalies].sort((left, right) => {
    const leftRank = priority.indexOf(left.metric_name);
    const rightRank = priority.indexOf(right.metric_name);
    return (
      (leftRank < 0 ? priority.length : leftRank) -
      (rightRank < 0 ? priority.length : rightRank)
    );
  })[0];
  if (!anomaly) return null;

  const baseline = baselineMetrics.find(
    (item) => item.id === anomaly.baseline_observation_id,
  );
  const current = currentMetrics.find(
    (item) => item.id === anomaly.current_observation_id,
  );
  if (
    !baseline ||
    !current ||
    baseline.value === null ||
    current.value === null
  ) {
    return null;
  }
  const unit = current.unit ?? baseline.unit;
  return {
    metricName: anomaly.metric_name,
    metricLabel: metricLabel(anomaly.metric_name),
    baselineMetricId: baseline.id,
    currentMetricId: current.id,
    baselineValueLabel: formatMetricValue(
      baseline.value,
      unit,
      anomaly.metric_name,
    ),
    currentValueLabel: formatMetricValue(
      current.value,
      unit,
      anomaly.metric_name,
    ),
    changeLabel: formatMetricChange(
      anomaly.absolute_change,
      unit,
      anomaly.metric_name,
    ),
    direction:
      anomaly.direction === "increase"
        ? "increase"
        : anomaly.direction === "decrease"
          ? "decrease"
          : "unknown",
  };
}

function selectPrimaryEvidence(
  evidence: CommerceEvidence[],
  comparison: CommerceMetricComparisonViewModel | null,
): CommerceEvidence | undefined {
  if (comparison) {
    const matched = evidence.find(
      (item) =>
        item.metric_observation_ids.includes(comparison.baselineMetricId) ||
        item.metric_observation_ids.includes(comparison.currentMetricId),
    );
    if (matched) return matched;
  }
  return evidence.find((item) => item.relation === "supports") ?? evidence[0];
}

function projectEvidenceInspector({
  evidence,
  comparison,
  periodLabel,
  analysisAvailable,
}: {
  evidence: CommerceEvidence;
  comparison: CommerceMetricComparisonViewModel | null;
  periodLabel: string;
  analysisAvailable: boolean;
}): CommerceEvidenceInspectorViewModel {
  const projected = projectEvidence(evidence);
  return {
    evidenceId: evidence.id,
    title: comparison ? `${comparison.metricLabel}变化` : "当前证据",
    statusLabel: projected.statusLabel,
    typeLabel:
      projected.typeLabel === "指标" ? "指标证据" : projected.typeLabel,
    relationLabel:
      evidence.relation === "supports"
        ? "支持"
        : evidence.relation === "contradicts"
          ? "反驳"
          : "背景信息",
    periodLabel,
    baselineValueLabel: comparison?.baselineValueLabel ?? "不可用",
    currentValueLabel: comparison?.currentValueLabel ?? "不可用",
    changeLabel: comparison?.changeLabel ?? "不可用",
    sourceLabel: comparison
      ? metricSourceLabel(comparison.metricName)
      : "已持久化经营数据",
    formulaLabel: comparison
      ? metricFormulaLabel(comparison.metricName)
      : "计算口径待查看",
    lineageLabel: analysisAvailable ? "完整" : "不可用",
  };
}

function projectOverviewAction(
  actions: CommerceCaseActionSummary[],
  primaryPath: string | null,
): CommerceCaseOverviewViewModel["action"] {
  const latest = [...actions].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  )[0];
  if (!latest) {
    return {
      id: null,
      title: "尚无候选行动",
      statusLabel: "调查结论满足行动门槛后才会创建候选行动。",
      available: false,
    };
  }
  return {
    id: latest.id,
    title: localizedActionTitle(latest, primaryPath),
    statusLabel: actionStatusLabel(latest.status),
    available: true,
  };
}

function localizedActionTitle(
  action: CommerceCaseActionSummary,
  primaryPath: string | null,
): string {
  if (CHINESE_TEXT.test(action.title)) return action.title;
  if (action.kind === "create_internal_task" && primaryPath === "fulfillment") {
    return "审查承运商服务等级与超时订单分布";
  }
  const labels: Readonly<Record<string, string>> = {
    no_op: "保留当前结论，不执行外部操作",
    export_audit_cohort: "导出可审计问题订单清单",
    create_internal_task: "创建内部复核任务",
    create_metric_monitor: "创建经营指标跟踪",
    request_missing_data: "请求补充缺失经营数据",
    external_mutation: "执行受策略约束的外部操作",
  };
  return labels[action.kind] ?? "查看候选行动";
}

function actionStatusLabel(status: string): string {
  const labels: Readonly<Record<string, string>> = {
    draft: "尚未执行",
    validating: "正在校验",
    policy_checked: "尚未执行",
    awaiting_approval: "等待审批",
    approved: "已批准，等待执行",
    rejected: "审批已拒绝",
    executing: "执行中",
    succeeded: "已执行，等待跟踪",
    failed: "执行失败",
    monitoring: "跟踪中",
    effective: "跟踪结果：有效",
    ineffective: "跟踪结果：无效",
    inconclusive: "跟踪结果：结论不足",
    rolling_back: "正在回滚",
    rolled_back: "已回滚",
  };
  return labels[status] ?? "状态待确认";
}

function conclusionDescription(
  primaryPath: string | null,
  latestHypothesis: CommerceHypothesis | undefined,
): string {
  if (latestHypothesis?.status === "contradicted") {
    return "当前工作假设已被证据否定，需要重新规划调查方向。";
  }
  if (primaryPath === "fulfillment") {
    return "当前证据支持履约异常确实存在，但现有数据不足以确认承运表现与异常之间的因果关系。";
  }
  if (primaryPath === "review_experience") {
    return "当前证据支持评价体验异常确实存在，但现有数据不足以确认具体原因的因果关系。";
  }
  if (primaryPath === "seller_peer") {
    return "当前证据显示目标卖家与同类群体存在差异，但对标结果不构成因果解释。";
  }
  return "当前结论只描述已核验证据范围内的关联，不确认因果关系。";
}

function verificationLabel(hasVerification: boolean, verdict: string | null) {
  if (!hasVerification) return "尚未完成独立验证";
  if (verdict === "failed") return "独立验证未通过，当前结论需要复核";
  return "独立验证通过，保留因果限制";
}

function analysisUnavailableReasonLabel(reason: string | null): string {
  const labels: Readonly<Record<string, string>> = {
    analysis_reader_unconfigured: "确定性分析读取尚未配置",
    lineage_not_found: "案例数据血缘不可用",
    artifact_not_found: "案例分析产物不可用",
    artifact_hash_mismatch: "案例分析产物未通过完整性校验",
    artifact_invalid: "案例分析产物合同不兼容",
    capability_mismatch: "当前数据能力与案例分析上下文不一致",
  };
  return reason
    ? (labels[reason] ?? "确定性分析当前不可用")
    : "确定性分析当前不可用";
}

function metricLabel(metricName: string): string {
  return METRIC_LABELS[metricName] ?? "经营指标";
}

function metricSourceLabel(metricName: string): string {
  if (
    [
      "late_delivery_rate",
      "handling_time_hours",
      "transit_time_hours",
      "delivery_duration_hours",
    ].includes(metricName)
  ) {
    return "订单履约数据";
  }
  if (["average_review_score", "low_rating_rate"].includes(metricName)) {
    return "评价数据";
  }
  if (metricName === "peer_late_delivery_rate") return "同类卖家对标数据";
  return "已持久化经营数据";
}

function metricFormulaLabel(metricName: string): string {
  const labels: Readonly<Record<string, string>> = {
    late_delivery_rate: "延迟订单数 / 已履约订单数",
    handling_time_hours: "下单至发货的平均小时数",
    transit_time_hours: "发货至签收的平均小时数",
    delivery_duration_hours: "下单至签收的平均小时数",
    average_review_score: "有效评价得分总和 / 有效评价数",
    low_rating_rate: "低分评价数 / 有效评价数",
    peer_late_delivery_rate: "同类卖家延迟订单数 / 同类卖家已履约订单数",
  };
  return labels[metricName] ?? "查看指标定义";
}

function formatMetricValue(
  rawValue: string,
  unit: string | null,
  metricName: string,
): string {
  const value = Number(rawValue);
  if (!Number.isFinite(value)) return "不可用";
  if (unit === "ratio" || metricName.endsWith("_rate")) {
    return `${formatNumber(value * 100)}%`;
  }
  if (unit === "hours" || metricName.endsWith("_hours")) {
    return `${formatNumber(value)} 小时`;
  }
  if (metricName === "average_review_score") {
    return `${formatNumber(value)} 分`;
  }
  return formatNumber(value);
}

function formatMetricChange(
  rawValue: string,
  unit: string | null,
  metricName: string,
): string {
  const value = Number(rawValue);
  if (!Number.isFinite(value)) return "变化不可用";
  const prefix = value > 0 ? "+" : "";
  if (unit === "ratio" || metricName.endsWith("_rate")) {
    return `${prefix}${formatNumber(value * 100)} 个百分点`;
  }
  if (unit === "hours" || metricName.endsWith("_hours")) {
    return `${prefix}${formatNumber(value)} 小时`;
  }
  if (metricName === "average_review_score") {
    return `${prefix}${formatNumber(value)} 分`;
  }
  return `${prefix}${formatNumber(value)}`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 1,
    minimumFractionDigits: Number.isInteger(value) ? 0 : 1,
  }).format(value);
}

function formatAnalysisPeriod(startValue: string, endValue: string): string {
  const start = new Date(startValue);
  const rawEnd = new Date(endValue);
  const end =
    rawEnd.getUTCHours() === 0 &&
    rawEnd.getUTCMinutes() === 0 &&
    rawEnd.getUTCSeconds() === 0
      ? new Date(rawEnd.getTime() - 1)
      : rawEnd;
  const format = (value: Date) =>
    `${value.getUTCMonth() + 1}月${value.getUTCDate()}日`;
  return `${format(start)}—${format(end)}`;
}

function formatUpdatedTime(value: string): string {
  return `更新于 ${new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value))}`;
}

function projectEvidence(item: CommerceEvidence): CommerceEvidenceViewModel {
  const relation =
    item.relation === "supports"
      ? "supports"
      : item.relation === "contradicts"
        ? "contradicts"
        : "unknown";
  const hasMetrics = item.metric_observation_ids.length > 0;
  const hasFacts = item.fact_ids.length > 0;
  const typeLabel =
    hasMetrics && hasFacts
      ? "综合证据"
      : hasMetrics
        ? "指标"
        : hasFacts
          ? "事实"
          : "证据";
  let summary = CHINESE_TEXT.test(item.summary)
    ? item.summary
    : hasMetrics && hasFacts
      ? "指标变化已由可追溯事实支持"
      : hasMetrics
        ? "发现可追溯的指标变化"
        : hasFacts
          ? "发现可追溯的业务事实"
          : "发现一条可追溯证据";
  if (relation === "contradicts") {
    summary = "发现与当前假设相矛盾的证据";
  }
  return {
    id: item.id,
    typeLabel,
    summary,
    statusLabel: item.semantic_status === "unknown" ? "待核验" : "已核验",
    relation,
  };
}

function projectHypothesisState(hypotheses: CommerceHypothesis[]) {
  const latest = [...hypotheses].sort(
    (left, right) => right.version - left.version,
  )[0];
  if (!latest) {
    return {
      label: "尚无工作假设",
      description: "需要先获得足够证据，才能形成可核验的工作假设。",
    };
  }
  if (latest.status === "supported") {
    return {
      label: "假设获得证据支持",
      description: "当前结论仍受证据范围和数据能力限制。",
    };
  }
  if (latest.status === "contradicted") {
    return {
      label: "假设已被证据否定",
      description: "系统需要重新规划调查角度。",
    };
  }
  return {
    label: "假设仍待核验",
    description: "当前证据尚不足以稳定支持或否定该假设。",
  };
}

function orderEvents(events: CommerceDomainEvent[]) {
  const originalIds = events.map((item) => item.id);
  const items = events
    .map((item, originalIndex) => ({ item, originalIndex }))
    .sort((left, right) => {
      const leftSequence = left.item.case_sequence;
      const rightSequence = right.item.case_sequence;
      if (leftSequence !== null && rightSequence !== null) {
        const sequenceOrder = leftSequence - rightSequence;
        if (sequenceOrder !== 0) return sequenceOrder;
      }
      const timeOrder =
        Date.parse(left.item.occurred_at) - Date.parse(right.item.occurred_at);
      return timeOrder !== 0
        ? timeOrder
        : left.originalIndex - right.originalIndex;
    })
    .map(({ item }) => item);
  return {
    items,
    wasReordered: items.some((item, index) => item.id !== originalIds[index]),
  };
}

function projectTimelineItem(
  event: CommerceDomainEvent,
): CommerceTimelineItemViewModel {
  const path = payloadString(event, "path_type");
  const pathName = path ? pathLabel(path) : "证据路径";
  const common = {
    id: event.id,
    timeLabel: formatEventTime(event.occurred_at),
  };

  switch (event.event_type) {
    case "case.created":
      return {
        ...common,
        kind: "known",
        title: "案例已创建",
        description: "已创建本次诊断案例，锁定分析范围与核心问题。",
        state: "completed",
      };
    case "run.created":
      return {
        ...common,
        kind: "known",
        title: "调查已开始",
        description: "已创建调查运行，等待调度所需的证据路径。",
        state: "running",
      };
    case "path.started":
      return {
        ...common,
        kind: "known",
        title: `${pathName}已开始`,
        description: `${pathName}正在收集和分析允许范围内的证据。`,
        state: "running",
      };
    case "path.completed":
      return {
        ...common,
        kind: "known",
        title: `${pathName}已完成`,
        description: `${pathName}已提交可追溯证据，等待统一校验。`,
        state: "completed",
      };
    case "path.blocked":
      return {
        ...common,
        kind: "known",
        title: `${pathName}已阻塞`,
        description: `${pathName}因数据能力、策略或外部结果不明确而停止。`,
        state: "blocked",
      };
    case "evidence.barrier_released":
      return {
        ...common,
        kind: "known",
        title: "证据校验通过",
        description: "本轮所需证据已持久化，可以进入结论综合与独立验证。",
        state: "completed",
      };
    case "verification.started":
      return {
        ...common,
        kind: "known",
        title: "独立验证已开始",
        description: "系统使用新鲜上下文核验结论与证据是否一致。",
        state: "running",
      };
    case "verification.completed":
      return {
        ...common,
        kind: "known",
        title: "独立验证完成",
        description: "结论已完成独立验证，结果已写入当前调查运行。",
        state: "completed",
      };
    case "lead.waiting":
      return {
        ...common,
        kind: "known",
        title: "等待用户输入",
        description: "调查已安全暂停，收到所需信息后可以继续。",
        state: "blocked",
      };
    case "lead.stopped":
      return {
        ...common,
        kind: "known",
        title: "目标循环已停止",
        description: "系统已根据目标、证据、预算或策略条件停止本轮调查。",
        state: "completed",
      };
    case "run.lease_released":
      return {
        ...common,
        kind: "known",
        title: "运行资源已释放",
        description: "本轮运行租约已经释放，不再占用执行资源。",
        state: "completed",
      };
    default:
      return {
        ...common,
        kind: "unknown",
        title: "未知事件",
        description: "收到暂不支持展示的结构化事件。",
        state: "neutral",
      };
  }
}

function projectSubagents(
  events: CommerceDomainEvent[],
  latestRun: CommerceRun | null,
): CommerceSubagentViewModel[] {
  const states = new Map<string, CommerceSubagentViewModel>();
  for (const requestedPath of latestRun?.requested_paths ?? []) {
    states.set(requestedPath, {
      pathType: requestedPath,
      label: pathLabel(requestedPath),
      status: "waiting",
      statusLabel: "等待调度",
    });
  }
  for (const event of events) {
    const pathType = payloadString(event, "path_type");
    if (!pathType) continue;
    if (event.event_type === "path.started") {
      states.set(pathType, {
        pathType,
        label: pathLabel(pathType),
        status: "running",
        statusLabel: "运行中",
      });
    } else if (event.event_type === "path.completed") {
      states.set(pathType, {
        pathType,
        label: pathLabel(pathType),
        status: "completed",
        statusLabel: "已完成",
      });
    } else if (event.event_type === "path.blocked") {
      states.set(pathType, {
        pathType,
        label: pathLabel(pathType),
        status: "blocked",
        statusLabel: "已阻塞",
      });
    }
  }
  return [...states.values()].sort((left, right) =>
    left.label.localeCompare(right.label, "zh-CN"),
  );
}

function projectEvidenceSources(evidence: CommerceEvidence[]) {
  const metricCount = evidence.filter(
    (item) => item.metric_observation_ids.length > 0,
  ).length;
  const factCount = evidence.filter((item) => item.fact_ids.length > 0).length;
  const contradictingCount = evidence.filter(
    (item) => item.relation === "contradicts",
  ).length;
  return [
    { label: "指标证据", count: metricCount },
    { label: "事实证据", count: factCount },
    { label: "矛盾证据", count: contradictingCount },
  ].filter((item) => item.count > 0);
}

function projectRuntime(
  events: CommerceDomainEvent[],
  latestRun: CommerceRun | null,
) {
  const verification = [...events]
    .reverse()
    .find((item) => item.event_type === "verification.completed");
  const modelIdentity = verification
    ? payloadString(verification, "actual_model_identity")
    : null;
  const retryCount = verification
    ? payloadNumber(verification, "retry_count")
    : null;
  const leaseReleased = events.some(
    (item) => item.event_type === "run.lease_released",
  );
  return {
    modelLabel:
      modelIdentity?.startsWith("deepseek-v4") === true
        ? "深度求索 V4"
        : modelIdentity
          ? "已记录模型身份"
          : "尚无模型调用",
    retryLabel:
      retryCount === 0
        ? "未重试"
        : retryCount === null
          ? "暂无重试记录"
          : `已重试 ${retryCount} 次`,
    leaseLabel: leaseReleased ? "租约已释放" : "租约状态待确认",
    stateLabel: latestRun
      ? runStatusLabel(latestRun.status)
      : "当前没有运行中的调查",
  };
}

function latestByUpdatedAt(runs: CommerceRun[]): CommerceRun | null {
  return (
    [...runs].sort(
      (left, right) =>
        Date.parse(right.updated_at) - Date.parse(left.updated_at),
    )[0] ?? null
  );
}

function inferPrimaryPath(events: CommerceDomainEvent[]): string | null {
  const completed = events.find(
    (item) =>
      item.event_type === "path.completed" &&
      payloadString(item, "path_type") === "fulfillment",
  );
  if (completed) return "fulfillment";
  const anyPath = events.find((item) => item.event_type.startsWith("path."));
  return anyPath ? payloadString(anyPath, "path_type") : null;
}

function pathLabel(pathType: string): string {
  return PATH_LABELS[pathType] ?? "其他分析";
}

function runStatusLabel(status: string): string {
  const labels: Readonly<Record<string, string>> = {
    queued: "等待调度",
    running: "调查运行中",
    waiting: "等待用户输入",
    completed: "调查已完成",
    blocked: "调查已阻塞",
    failed: "调查运行失败",
    cancelled: "调查已取消",
  };
  return labels[status] ?? "运行状态待确认";
}

function payloadString(event: CommerceDomainEvent, key: string): string | null {
  const value = event.payload[key];
  return typeof value === "string" ? value : null;
}

function payloadNumber(event: CommerceDomainEvent, key: string): number | null {
  const value = event.payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatEventTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function labelFromMap(
  labels: Readonly<Record<string, string>>,
  value: string,
  fallback: string,
): string {
  return labels[value] ?? fallback;
}
