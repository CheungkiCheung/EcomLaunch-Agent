import {
  type CommerceCaseDetail,
  type CommerceEvidence,
  type CommerceHypothesis,
  type CommerceMetricObservation,
} from "./types";

const CHINESE_TEXT = /[\u3400-\u9fff]/u;

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

const SEMANTIC_STATUS_LABELS: Readonly<Record<string, string>> = {
  observed: "已观察",
  derived: "已推导",
  estimated: "已估算",
  hypothesis: "待验证",
  unknown: "未知",
  blocked: "已阻塞",
};

const HYPOTHESIS_STATUS_LABELS: Readonly<Record<string, string>> = {
  proposed: "待调查",
  investigating: "调查中",
  supported: "已支持",
  contradicted: "已反驳",
  rejected: "已拒绝",
  unknown: "未知",
  blocked: "已阻塞",
};

export type CommerceEvidenceFilter =
  | "all"
  | "supports"
  | "contradicts"
  | "unknown";

export interface CommerceEvidenceReferenceViewModel {
  id: string;
  kind: "metric" | "fact";
  label: string;
  valueLabel: string;
  metadataLabel: string;
}

export interface CommerceEvidenceHypothesisViewModel {
  id: string;
  label: string;
  statusLabel: string;
  relationLabel: "支持当前判断" | "反驳当前判断";
}

export interface CommerceEvidenceExplorerItemViewModel {
  id: string;
  shortId: string;
  summary: string;
  relation: Exclude<CommerceEvidenceFilter, "all">;
  relationLabel: "支持" | "矛盾" | "未知";
  typeLabel: string;
  semanticStatusLabel: string;
  confidenceLabel: string;
  referenceCountLabel: string;
  references: CommerceEvidenceReferenceViewModel[];
  hypotheses: CommerceEvidenceHypothesisViewModel[];
  boundary: string;
}

export interface CommerceEvidenceExplorerViewModel {
  title: string;
  subtitle: string;
  filters: Array<{
    value: CommerceEvidenceFilter;
    label: string;
    count: number;
  }>;
  items: CommerceEvidenceExplorerItemViewModel[];
}

export function buildCommerceEvidenceExplorerViewModel(
  detail: CommerceCaseDetail,
): CommerceEvidenceExplorerViewModel {
  const baselineIds = new Set(
    detail.analysis.baseline_metrics.map((item) => item.id),
  );
  const currentIds = new Set(
    detail.analysis.current_metrics.map((item) => item.id),
  );
  const metrics = new Map(
    [
      ...detail.analysis.baseline_metrics,
      ...detail.analysis.current_metrics,
    ].map((item) => [item.id, item]),
  );
  const items = detail.evidence.map((evidence) =>
    projectEvidenceExplorerItem({
      evidence,
      hypotheses: detail.hypotheses,
      metrics,
      baselineIds,
      currentIds,
    }),
  );
  return {
    title: "证据浏览",
    subtitle: "逐条检查支持、矛盾和未知证据，以及它们引用的事实与指标。",
    filters: [
      filterOption("all", "全部", items),
      filterOption("supports", "支持", items),
      filterOption("contradicts", "矛盾", items),
      filterOption("unknown", "未知", items),
    ],
    items,
  };
}

export function filterCommerceEvidenceExplorerItems(
  items: readonly CommerceEvidenceExplorerItemViewModel[],
  options: { filter: CommerceEvidenceFilter; query: string },
): CommerceEvidenceExplorerItemViewModel[] {
  const query = options.query.trim().toLocaleLowerCase("zh-CN");
  return items.filter((item) => {
    if (options.filter !== "all" && item.relation !== options.filter) {
      return false;
    }
    if (!query) return true;
    return evidenceSearchText(item).includes(query);
  });
}

function filterOption(
  value: CommerceEvidenceFilter,
  label: string,
  items: readonly CommerceEvidenceExplorerItemViewModel[],
) {
  return {
    value,
    label,
    count:
      value === "all"
        ? items.length
        : items.filter((item) => item.relation === value).length,
  };
}

function projectEvidenceExplorerItem({
  evidence,
  hypotheses,
  metrics,
  baselineIds,
  currentIds,
}: {
  evidence: CommerceEvidence;
  hypotheses: CommerceHypothesis[];
  metrics: Map<string, CommerceMetricObservation>;
  baselineIds: Set<string>;
  currentIds: Set<string>;
}): CommerceEvidenceExplorerItemViewModel {
  const relation = evidenceRelation(evidence);
  const metricReferences = evidence.metric_observation_ids.map((id) =>
    projectMetricReference(id, metrics.get(id), baselineIds, currentIds),
  );
  const factReferences = evidence.fact_ids.map(projectFactReference);
  const references = [...metricReferences, ...factReferences];
  return {
    id: evidence.id,
    shortId: shortObjectId(evidence.id),
    summary: evidenceSummary(evidence, metricReferences),
    relation,
    relationLabel:
      relation === "supports"
        ? "支持"
        : relation === "contradicts"
          ? "矛盾"
          : "未知",
    typeLabel: evidenceTypeLabel(evidence),
    semanticStatusLabel:
      SEMANTIC_STATUS_LABELS[evidence.semantic_status] ?? "状态待确认",
    confidenceLabel: `${Math.round(evidence.confidence * 100)}%`,
    referenceCountLabel: `引用 ${references.length} 个对象`,
    references,
    hypotheses: projectEvidenceHypotheses(evidence, hypotheses),
    boundary: evidenceBoundary(relation, evidence.semantic_status),
  };
}

function projectMetricReference(
  id: string,
  metric: CommerceMetricObservation | undefined,
  baselineIds: Set<string>,
  currentIds: Set<string>,
): CommerceEvidenceReferenceViewModel {
  if (!metric) {
    return {
      id,
      kind: "metric",
      label: `指标 ${shortObjectId(id)}`,
      valueLabel: "指标详情不可用",
      metadataLabel: "引用未在当前案例分析中恢复",
    };
  }
  const periodPrefix = baselineIds.has(id)
    ? "基线"
    : currentIds.has(id)
      ? "当前"
      : "引用";
  return {
    id,
    kind: "metric",
    label: `${periodPrefix}${metricLabel(metric.metric_name)}`,
    valueLabel: formatMetricValue(metric),
    metadataLabel: metricWindowLabel(metric),
  };
}

function projectFactReference(id: string): CommerceEvidenceReferenceViewModel {
  return {
    id,
    kind: "fact",
    label: `事实 ${shortObjectId(id)}`,
    valueLabel: "原始事实详情尚未开放",
    metadataLabel: "保留可审计事实编号",
  };
}

function evidenceSummary(
  evidence: CommerceEvidence,
  metricReferences: CommerceEvidenceReferenceViewModel[],
): string {
  if (CHINESE_TEXT.test(evidence.summary)) return evidence.summary;
  if (metricReferences.length >= 2) {
    const first = metricReferences[0];
    const second = metricReferences[1];
    const firstMetric = first?.label.replace(/^(基线|当前|引用)/u, "");
    const secondMetric = second?.label.replace(/^(基线|当前|引用)/u, "");
    if (first && second && firstMetric === secondMetric) {
      return `${firstMetric}从 ${first.valueLabel} 变为 ${second.valueLabel}`;
    }
  }
  if (metricReferences[0]) {
    const reference = metricReferences[0];
    return `${reference.label}为 ${reference.valueLabel}`;
  }
  if (evidence.fact_ids.length > 0) return "发现一条可追溯的事实证据";
  return "当前证据摘要尚未完成中文投影";
}

function projectEvidenceHypotheses(
  evidence: CommerceEvidence,
  hypotheses: CommerceHypothesis[],
): CommerceEvidenceHypothesisViewModel[] {
  const linked: CommerceEvidenceHypothesisViewModel[] = [];
  for (const hypothesis of hypotheses) {
    const supports = hypothesis.supporting_evidence_ids.includes(evidence.id);
    const contradicts = hypothesis.contradicting_evidence_ids.includes(
      evidence.id,
    );
    if (!supports && !contradicts) continue;
    linked.push({
      id: hypothesis.id,
      label: CHINESE_TEXT.test(hypothesis.statement)
        ? hypothesis.statement
        : "当前工作假设",
      statusLabel: HYPOTHESIS_STATUS_LABELS[hypothesis.status] ?? "状态待确认",
      relationLabel: supports ? "支持当前判断" : "反驳当前判断",
    });
  }
  return linked;
}

function evidenceRelation(
  evidence: CommerceEvidence,
): Exclude<CommerceEvidenceFilter, "all"> {
  if (evidence.relation === "supports") return "supports";
  if (evidence.relation === "contradicts") return "contradicts";
  return "unknown";
}

function evidenceTypeLabel(evidence: CommerceEvidence): string {
  const metrics = evidence.metric_observation_ids.length > 0;
  const facts = evidence.fact_ids.length > 0;
  if (metrics && facts) return "综合证据";
  if (metrics) return "指标证据";
  if (facts) return "事实证据";
  return "边界证据";
}

function evidenceBoundary(
  relation: Exclude<CommerceEvidenceFilter, "all">,
  semanticStatus: string,
): string {
  if (semanticStatus === "unknown" || semanticStatus === "blocked") {
    return "当前对象用于记录未知或阻塞边界，不能作为已观察事实。";
  }
  if (relation === "contradicts") {
    return "该证据反驳部分判断，应与支持证据共同审查。";
  }
  if (relation === "unknown") {
    return "该对象提供调查背景，不能单独支持或反驳当前判断。";
  }
  return "该证据支持当前判断，但不能单独证明因果关系。";
}

function evidenceSearchText(item: CommerceEvidenceExplorerItemViewModel) {
  return [
    item.summary,
    item.relationLabel,
    item.typeLabel,
    item.semanticStatusLabel,
    ...item.references.flatMap((reference) => [
      reference.label,
      reference.valueLabel,
      reference.metadataLabel,
    ]),
    ...item.hypotheses.flatMap((hypothesis) => [
      hypothesis.label,
      hypothesis.statusLabel,
      hypothesis.relationLabel,
    ]),
  ]
    .join(" ")
    .toLocaleLowerCase("zh-CN");
}

function metricLabel(name: string): string {
  return METRIC_LABELS[name] ?? "经营指标";
}

function formatMetricValue(metric: CommerceMetricObservation): string {
  if (metric.value === null) return "未观察";
  const value = Number(metric.value);
  if (!Number.isFinite(value)) return metric.value;
  if (metric.unit === "ratio") return `${trimNumber(value * 100)}%`;
  if (metric.unit === "hours") return `${trimNumber(value)} 小时`;
  if (metric.unit === "score") return `${trimNumber(value)} 分`;
  if (metric.unit === "count") return `${trimNumber(value)} 个`;
  return trimNumber(value);
}

function metricWindowLabel(metric: CommerceMetricObservation): string {
  if (!metric.window_start || !metric.window_end) return "窗口未提供";
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
  });
  return `${formatter.format(new Date(metric.window_start))}—${formatter.format(new Date(metric.window_end))}`;
}

function trimNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
  }).format(value);
}

function shortObjectId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 4)}…${id.slice(-6)}` : id;
}
