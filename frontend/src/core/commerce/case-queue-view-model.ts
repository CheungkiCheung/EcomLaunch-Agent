import { type CommerceExplicitCasePath } from "./api";
import { type CommerceCase, type CommerceDataInboxSnapshot } from "./types";

const CHINESE_TEXT = /[\u3400-\u9fff]/u;

const SEVERITY_LABELS: Readonly<Record<string, string>> = {
  critical: "紧急",
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

const SEVERITY_RANK: Readonly<Record<string, number>> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

const STATUS_LABELS: Readonly<Record<string, string>> = {
  new: "待调查",
  triaged: "已分诊",
  investigating: "调查中",
  awaiting_data: "等待数据",
  awaiting_approval: "等待审批",
  action_in_progress: "行动执行中",
  monitoring: "跟踪中",
  resolved: "已解决",
  reopened: "已重新打开",
  inconclusive: "结论不足",
  blocked: "已阻塞",
  cancelled: "已取消",
};

const ACTION_LABELS: Readonly<Record<string, string>> = {
  awaiting_data: "补充数据",
  awaiting_approval: "查看审批",
  action_in_progress: "查看执行",
  monitoring: "查看跟踪",
  resolved: "查看结果",
  cancelled: "查看记录",
};

const STATUS_FALLBACKS: Readonly<Record<string, string>> = {
  new: "案例已创建，尚未开始调查。",
  triaged: "案例已完成分诊，等待后续处理。",
  investigating: "调查正在进行，等待新的结构化结果。",
  awaiting_data: "等待补充数据后继续判断。",
  awaiting_approval: "候选行动正在等待人工审批。",
  action_in_progress: "已批准行动正在执行。",
  monitoring: "等待新数据进入后重新计算。",
  resolved: "当前案例已解决，可查看完整记录。",
  reopened: "新证据到来后，案例已重新打开。",
  inconclusive: "现有证据不足以形成可靠结论。",
  blocked: "案例因数据、策略或外部状态而阻塞。",
  cancelled: "当前案例已取消，历史记录仍可审计。",
};

export type CommerceCaseQueueFilter =
  | "all"
  | "investigation"
  | "awaiting_data"
  | "awaiting_approval"
  | "action_in_progress"
  | "monitoring";

export interface CommerceCaseQueueItemViewModel {
  id: string;
  title: string;
  summary: string;
  status: string;
  statusLabel: string;
  severity: string;
  severityLabel: string;
  actionLabel: string;
  updatedLabel: string;
}

export interface CommerceCaseQueueViewModel {
  status: "empty" | "ready";
  title: string;
  subtitle: string;
  filters: Array<{
    value: CommerceCaseQueueFilter;
    label: string;
    count: number;
  }>;
  attentionItems: CommerceCaseQueueItemViewModel[];
  trackingItems: CommerceCaseQueueItemViewModel[];
  closedItems: CommerceCaseQueueItemViewModel[];
  resultCount: number;
}

export interface CommerceCaseCreatePathOption {
  value: CommerceExplicitCasePath;
  capabilityName: string;
  label: string;
  statusLabel: string;
  disabled: boolean;
  selected: boolean;
}

export interface CommerceCaseCreateOptions {
  datasetId: string;
  datasetLabel: string;
  sellerSuggestions: string[];
  pathOptions: CommerceCaseCreatePathOption[];
}

export interface CommerceExplicitCaseDraft {
  sellerId: string;
  baselineStart: string;
  baselineEnd: string;
  currentStart: string;
  currentEnd: string;
  requestedPaths: CommerceExplicitCasePath[];
  peerProductCategory: string;
  peerMinOrders: number;
  matchSellerState: boolean;
}

const INVESTIGATION_STATUSES = new Set([
  "new",
  "triaged",
  "investigating",
  "reopened",
  "inconclusive",
  "blocked",
]);
const CLOSED_STATUSES = new Set(["resolved", "cancelled"]);

const CREATE_PATHS: ReadonlyArray<{
  capabilityName: string;
  value: CommerceExplicitCasePath;
  label: string;
}> = [
  {
    capabilityName: "fulfillment_diagnosis",
    value: "fulfillment",
    label: "履约诊断",
  },
  {
    capabilityName: "review_experience",
    value: "review_experience",
    label: "评价体验",
  },
  {
    capabilityName: "seller_peer_comparison",
    value: "seller_peer",
    label: "卖家对标",
  },
];

export function buildCommerceCaseQueueViewModel(
  cases: readonly CommerceCase[],
  options: { filter: CommerceCaseQueueFilter; query: string },
): CommerceCaseQueueViewModel {
  const sorted = [...cases].sort(compareCases);
  const filters = [
    filterOption("all", "全部", sorted),
    filterOption("investigation", "待调查", sorted),
    filterOption("awaiting_data", "等待数据", sorted),
    filterOption("awaiting_approval", "等待审批", sorted),
    filterOption("action_in_progress", "执行中", sorted),
    filterOption("monitoring", "跟踪中", sorted),
  ];
  const query = options.query.trim().toLocaleLowerCase("zh-CN");
  const selected = sorted.filter(
    (item) =>
      matchesFilter(item, options.filter) &&
      (!query || searchableText(item).includes(query)),
  );
  const projected = selected.map(projectCase);
  return {
    status: cases.length === 0 ? "empty" : "ready",
    title: "需要处理的经营问题",
    subtitle: "集中查看待调查、待补数、待审批、执行中和跟踪中的案例。",
    filters,
    attentionItems: projected.filter(
      (item) =>
        item.status !== "monitoring" && !CLOSED_STATUSES.has(item.status),
    ),
    trackingItems: projected.filter((item) => item.status === "monitoring"),
    closedItems: projected.filter((item) => CLOSED_STATUSES.has(item.status)),
    resultCount: projected.length,
  };
}

export function buildCommerceCaseCreateOptions(
  snapshot: CommerceDataInboxSnapshot,
  preferredPath?: string | null,
): CommerceCaseCreateOptions | null {
  const dataset = snapshot.selectedDataset;
  if (!dataset) return null;
  const assessments = new Map(
    dataset.capabilities.capabilities.map((item) => [item.name, item]),
  );
  const normalizedPreferred = preferredPath?.trim() ?? "";
  const sellerMapping = dataset.mappings.mappings.find(
    (item) =>
      item.semantic_field === "seller.id" && item.status === "confirmed",
  );
  const sellerColumn = sellerMapping
    ? dataset.profile.tables
        .find((table) => table.table_name === sellerMapping.table_name)
        ?.columns.find((column) => column.name === sellerMapping.column_name)
    : undefined;
  return {
    datasetId: dataset.manifest.dataset_id,
    datasetLabel: `${dataset.manifest.files[0]?.original_name ?? "当前数据批次"} · ${dataset.checks.row_count.toLocaleString("zh-CN")} 行`,
    sellerSuggestions: [
      ...new Set(
        (sellerColumn?.example_values ?? [])
          .map((value) => value.trim())
          .filter(Boolean),
      ),
    ],
    pathOptions: CREATE_PATHS.map((path) => {
      const assessment = assessments.get(path.capabilityName);
      const status = assessment?.status ?? "unavailable";
      return {
        ...path,
        statusLabel:
          status === "available"
            ? "可直接分析"
            : status === "partial"
              ? "部分可分析"
              : "当前不可分析",
        disabled: status === "unavailable",
        selected:
          status !== "unavailable" &&
          (normalizedPreferred === path.capabilityName ||
            normalizedPreferred === path.value),
      };
    }),
  };
}

export function validateCommerceExplicitCaseDraft(
  draft: CommerceExplicitCaseDraft,
): string | null {
  if (!draft.sellerId.trim()) return "请填写经营主体（卖家编号）";
  if (
    !draft.baselineStart ||
    !draft.baselineEnd ||
    !draft.currentStart ||
    !draft.currentEnd
  ) {
    return "请完整填写基线窗口和当前窗口";
  }
  const baselineStart = Date.parse(draft.baselineStart);
  const baselineEnd = Date.parse(draft.baselineEnd);
  const currentStart = Date.parse(draft.currentStart);
  const currentEnd = Date.parse(draft.currentEnd);
  if (
    [baselineStart, baselineEnd, currentStart, currentEnd].some((value) =>
      Number.isNaN(value),
    )
  ) {
    return "分析窗口包含无效时间";
  }
  if (baselineStart >= baselineEnd) return "基线窗口的结束时间必须晚于开始时间";
  if (currentStart >= currentEnd) return "当前窗口的结束时间必须晚于开始时间";
  if (baselineEnd > currentStart) return "基线窗口必须在当前窗口开始前结束";
  if (draft.requestedPaths.length < 1) return "请至少选择一条分析路径";
  if (draft.requestedPaths.length > 3) return "最多选择三条分析路径";
  if (new Set(draft.requestedPaths).size !== draft.requestedPaths.length) {
    return "分析路径不能重复";
  }
  if (draft.requestedPaths.includes("seller_peer")) {
    if (!draft.peerProductCategory.trim()) {
      return "卖家对标需要填写商品类目口径";
    }
    if (!Number.isInteger(draft.peerMinOrders) || draft.peerMinOrders < 2) {
      return "卖家对标的最小订单数不能小于 2";
    }
  }
  return null;
}

function filterOption(
  value: CommerceCaseQueueFilter,
  label: string,
  cases: readonly CommerceCase[],
) {
  return {
    value,
    label,
    count: cases.filter((item) => matchesFilter(item, value)).length,
  };
}

function matchesFilter(
  item: CommerceCase,
  filter: CommerceCaseQueueFilter,
): boolean {
  if (filter === "all") return true;
  if (filter === "investigation")
    return INVESTIGATION_STATUSES.has(item.status);
  return item.status === filter;
}

function searchableText(item: CommerceCase): string {
  return [localizedTitle(item.title), item.title, item.summary ?? ""]
    .join(" ")
    .toLocaleLowerCase("zh-CN");
}

function projectCase(item: CommerceCase): CommerceCaseQueueItemViewModel {
  return {
    id: item.id,
    title: localizedTitle(item.title),
    summary: localizedSummary(item),
    status: item.status,
    statusLabel: STATUS_LABELS[item.status] ?? "状态待确认",
    severity: item.severity,
    severityLabel: SEVERITY_LABELS[item.severity] ?? "待分级",
    actionLabel: ACTION_LABELS[item.status] ?? "打开案例",
    updatedLabel: formatUpdatedAt(item.updated_at),
  };
}

function localizedTitle(title: string): string {
  if (CHINESE_TEXT.test(title)) return title;
  const normalized = title.toLocaleLowerCase("en-US");
  if (normalized.includes("review")) return "评价体验异常";
  if (normalized.includes("delivery") || normalized.includes("fulfillment")) {
    return "履约延迟异常";
  }
  if (normalized.includes("peer")) return "卖家对标检查";
  if (normalized.includes("user-requested")) return "用户发起的经营诊断";
  return "经营问题待确认";
}

function localizedSummary(item: CommerceCase): string {
  if (item.summary && CHINESE_TEXT.test(item.summary)) return item.summary;
  if (item.summary) {
    return STATUS_FALLBACKS[item.status] ?? "当前案例摘要尚未完成中文投影。";
  }
  return "当前案例尚未形成可展示摘要。";
}

function compareCases(left: CommerceCase, right: CommerceCase): number {
  const severity =
    (SEVERITY_RANK[right.severity] ?? 0) - (SEVERITY_RANK[left.severity] ?? 0);
  if (severity !== 0) return severity;
  return Date.parse(right.updated_at) - Date.parse(left.updated_at);
}

function formatUpdatedAt(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
