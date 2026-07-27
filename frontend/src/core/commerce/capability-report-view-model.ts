import { buildCommerceDataInboxViewModel } from "./data-inbox-view-model";
import type {
  CommerceCapabilityProfile,
  CommerceDataInboxSnapshot,
  CommerceDatasetDetail,
} from "./types";

const CAPABILITY_LABELS: Readonly<Record<string, string>> = {
  fulfillment_diagnosis: "履约诊断",
  review_experience: "评价体验",
  seller_peer_comparison: "卖家对标",
};

const CAPABILITY_DESCRIPTIONS: Readonly<Record<string, string>> = {
  fulfillment_diagnosis: "识别履约关键环节的问题",
  review_experience: "识别评价趋势与体验问题",
  seller_peer_comparison: "对比卖家在履约与评价方面的表现",
};

const STATUS_LABELS: Readonly<Record<string, string>> = {
  available: "可直接分析",
  partial: "部分可分析",
  unavailable: "当前不可分析",
};

const STATUS_DESCRIPTIONS: Readonly<Record<string, string>> = {
  available: "证据完整，可以进入案例队列",
  partial: "部分字段可用，结论范围会受到限制",
  unavailable: "当前数据不足，不能形成可靠判断",
};

const REASON_LABELS: Readonly<Record<string, string>> = {
  missing_required_semantics: "缺少必需字段",
  missing_optional_semantics: "缺少可选字段",
  unconfirmed_semantics: "有字段需要人工确认",
  insufficient_entity_diversity: "实体数量不足",
  dependency_unavailable: "依赖能力不可用",
};

const SEMANTIC_LABELS: Readonly<Record<string, string>> = {
  "order.id": "订单",
  "order.status": "订单状态",
  "order.purchased_at": "下单时间",
  "order.approved_at": "订单审核时间",
  "order.carrier_handoff_at": "发货时间",
  "order.delivered_at": "签收时间",
  "order.estimated_delivery_at": "预计送达时间",
  "order_item.order_id": "订单明细",
  "seller.id": "卖家",
  "product.id": "商品",
  "product.category": "商品",
  "review.order_id": "评价订单",
  "review.score": "评价评分",
  "review.title": "评价标题",
  "review.comment": "评价文本",
  "customer.id": "客户",
  "customer.unique_id": "客户",
  "customer.city": "客户",
  "customer.state": "客户",
};

export interface CommerceCapabilityPathViewModel {
  name: string;
  label: string;
  description: string;
  status: "available" | "partial" | "unavailable";
  statusLabel: string;
  statusDescription: string;
  reasonLabels: string[];
  availableFields: string[];
  missingFields: string[];
  canCreateCase: boolean;
}

export interface CommerceCapabilityReviewItem {
  tableName: string;
  columnName: string;
  semanticField: string;
  semanticLabel: string;
}

export interface CommerceCapabilityReportViewModel {
  status: "empty" | "ready";
  title: string;
  subtitle: string;
  metadataLabel: string | null;
  dataset: CommerceDatasetDetail | null;
  paths: CommerceCapabilityPathViewModel[];
  observedLabels: string[];
  notObservedLabels: readonly string[];
  reviewItems: CommerceCapabilityReviewItem[];
}

export function buildCommerceCapabilityReportViewModel(
  snapshot: CommerceDataInboxSnapshot,
): CommerceCapabilityReportViewModel {
  const dataset = snapshot.selectedDataset;
  if (!dataset) {
    return {
      status: "empty",
      title: "这批数据能分析什么",
      subtitle: "先接入并确认一批经营数据，系统才能判断可分析范围。",
      metadataLabel: null,
      dataset: null,
      paths: [],
      observedLabels: [],
      notObservedLabels: notObservedLabels(),
      reviewItems: [],
    };
  }

  const inbox = buildCommerceDataInboxViewModel(snapshot);
  return {
    status: "ready",
    title: "这批数据能分析什么",
    subtitle:
      "系统先根据已确认的字段、关联关系和样本量，明确可分析范围，再决定是否适合创建案例。",
    metadataLabel: `${inbox.title} · ${inbox.metadataLabel?.replace(" · 完整性检查通过", "") ?? "数据量待确认"}`,
    dataset,
    paths: projectPaths(dataset.capabilities),
    observedLabels: inbox.recognizedLabels,
    notObservedLabels: inbox.notObservedLabels,
    reviewItems: dataset.mappings.mappings
      .filter((mapping) => mapping.status === "needs_confirmation")
      .map((mapping) => ({
        tableName: mapping.table_name,
        columnName: mapping.column_name,
        semanticField: mapping.semantic_field,
        semanticLabel: semanticLabel(mapping.semantic_field),
      })),
  };
}

function projectPaths(
  profile: CommerceCapabilityProfile,
): CommerceCapabilityPathViewModel[] {
  return profile.capabilities.map((capability) => ({
    name: capability.name,
    label: CAPABILITY_LABELS[capability.name] ?? capability.name,
    description:
      CAPABILITY_DESCRIPTIONS[capability.name] ??
      "基于已确认数据生成可追溯分析",
    status: normalizeStatus(capability.status),
    statusLabel: STATUS_LABELS[capability.status] ?? "状态待确认",
    statusDescription:
      STATUS_DESCRIPTIONS[capability.status] ?? "当前状态需要进一步检查",
    reasonLabels: capability.reason_codes
      .map((reason) => REASON_LABELS[reason] ?? reason)
      .filter((reason) => reason !== "available"),
    availableFields: capability.available_fields.map(semanticLabel),
    missingFields: [
      ...capability.missing_required_fields,
      ...capability.missing_optional_fields,
    ].map(semanticLabel),
    canCreateCase: capability.status !== "unavailable",
  }));
}

function normalizeStatus(
  value: string,
): "available" | "partial" | "unavailable" {
  if (value === "available" || value === "partial") return value;
  return "unavailable";
}

function semanticLabel(field: string): string {
  return SEMANTIC_LABELS[field] ?? field;
}

function notObservedLabels(): readonly string[] {
  return ["曝光", "点击", "加购", "广告消耗", "库存", "利润"];
}
