import type {
  CommerceDataInboxSnapshot,
  CommerceDatasetDetail,
  CommerceDatasetListItem,
} from "./types";

const SEMANTIC_LABELS: Readonly<Record<string, string>> = {
  "order.id": "订单",
  "order.status": "订单状态",
  "order.purchased_at": "订单",
  "order.approved_at": "订单",
  "order.carrier_handoff_at": "履约",
  "order.delivered_at": "履约",
  "order.estimated_delivery_at": "履约",
  "order.customer_id": "客户",
  "order_item.order_id": "订单明细",
  "seller.id": "卖家",
  "product.id": "商品",
  "product.category": "商品",
  "review.order_id": "评价",
  "review.score": "评价",
  "review.title": "评价",
  "review.comment": "评价",
  "customer.id": "客户",
  "customer.unique_id": "客户",
  "customer.city": "客户",
  "customer.state": "客户",
  "seller.city": "卖家",
  "seller.state": "卖家",
};

const SEMANTIC_DETAIL_LABELS: Readonly<Record<string, string>> = {
  "order.purchased_at": "订单下单时间",
  "order.approved_at": "订单审核时间",
  "order.carrier_handoff_at": "承运交接时间",
  "order.delivered_at": "订单送达时间",
  "order.estimated_delivery_at": "预计送达时间",
};

const NOT_OBSERVED_LABELS = [
  "曝光",
  "点击",
  "加购",
  "广告消耗",
  "库存",
  "利润",
] as const;

export interface CommerceDataInboxFileRow {
  id: string;
  filename: string;
  roleLabel: string;
  rowLabel: string;
  statusLabel: "已识别";
  sourceLabel: string;
}

export interface CommerceDataInboxCheckRow {
  label: string;
  detail: string;
  state: "verified" | "review" | "unknown";
}

export interface CommerceDataInboxPendingConfirmation {
  tableName: string;
  columnName: string;
  semanticField: string;
  semanticLabel: string;
  title: string;
  description: string;
}

export interface CommerceDataInboxViewModel {
  status: "empty" | "review";
  title: string;
  subtitle: string;
  metadataLabel: string | null;
  files: CommerceDataInboxFileRow[];
  checks: CommerceDataInboxCheckRow[];
  pendingConfirmation: CommerceDataInboxPendingConfirmation | null;
  recognizedLabels: string[];
  notObservedLabels: readonly string[];
  recentDatasets: CommerceDatasetListItem[];
  selectedDataset: CommerceDatasetDetail | null;
}

export function buildCommerceDataInboxViewModel(
  snapshot: CommerceDataInboxSnapshot,
): CommerceDataInboxViewModel {
  const selected = snapshot.selectedDataset;
  if (!selected) {
    return {
      status: "empty",
      title: "接入经营数据",
      subtitle:
        "上传文件后，系统会先检查结构、字段语义和数据能力，再决定能够分析什么。",
      metadataLabel: null,
      files: [],
      checks: [],
      pendingConfirmation: null,
      recognizedLabels: [],
      notObservedLabels: NOT_OBSERVED_LABELS,
      recentDatasets: snapshot.datasets,
      selectedDataset: null,
    };
  }

  const tablesByName = new Map(
    selected.profile.tables.map((table) => [table.table_name, table]),
  );
  const files = selected.manifest.files.map((file) => {
    const table = selected.manifest.tables.find(
      (candidate) => candidate.source_file_id === file.id,
    );
    const profile = table ? tablesByName.get(table.table_name) : undefined;
    return {
      id: file.id,
      filename: file.original_name,
      roleLabel: table ? tableRoleLabel(table.table_name) : "数据文件",
      rowLabel: profile
        ? `${profile.row_count.toLocaleString("zh-CN")} 行`
        : "行数待确认",
      statusLabel: "已识别" as const,
      sourceLabel: file.archive_member ?? file.stored_relative_path,
    };
  });
  const pendingMapping = selected.mappings.mappings.find(
    (mapping) => mapping.status === "needs_confirmation",
  );
  const pendingConfirmation = pendingMapping
    ? {
        tableName: pendingMapping.table_name,
        columnName: pendingMapping.column_name,
        semanticField: pendingMapping.semantic_field,
        semanticLabel: semanticDetailLabel(pendingMapping.semantic_field),
        title: `确认${semanticDetailLabel(pendingMapping.semantic_field)}字段`,
        description: `字段 ${pendingMapping.column_name} 可能表示${semanticDetailLabel(
          pendingMapping.semantic_field,
        )}。确认后，系统才能稳定计算相关指标。`,
      }
    : null;
  const recognizedLabels = Array.from(
    new Set(
      selected.mappings.mappings
        .filter((mapping) => mapping.status === "confirmed")
        .map((mapping) => semanticLabel(mapping.semantic_field)),
    ),
  );
  const unresolvedCount = selected.mappings.unresolved_columns.length;

  return {
    status: "review",
    title: datasetTitle(selected),
    subtitle: `已接收 ${selected.manifest.files.length} 个文件，正在确认数据语义和可分析范围。`,
    metadataLabel: `${sumRows(selected)} 行 · ${selected.manifest.files.length} 个文件 · 完整性检查通过`,
    files,
    checks: [
      { label: "文件完整性", detail: "通过", state: "verified" },
      {
        label: "表结构",
        detail: `${selected.manifest.tables.length} 张表`,
        state: "verified",
      },
      {
        label: "关联关系",
        detail:
          selected.profile.join_risks.length > 0
            ? `${selected.profile.join_risks.length} 组可连接`
            : "未发现可连接关系",
        state: selected.profile.join_risks.length > 0 ? "verified" : "unknown",
      },
      {
        label: "字段语义",
        detail: unresolvedCount > 0 ? `${unresolvedCount} 项需确认` : "已确认",
        state: unresolvedCount > 0 ? "review" : "verified",
      },
    ],
    pendingConfirmation,
    recognizedLabels,
    notObservedLabels: NOT_OBSERVED_LABELS,
    recentDatasets: snapshot.datasets,
    selectedDataset: selected,
  };
}

function datasetTitle(dataset: CommerceDatasetDetail): string {
  const tableNames = dataset.manifest.tables.map((table) => table.table_name);
  if (tableNames.some((name) => name.includes("order"))) return "订单履约数据";
  return "经营数据批次";
}

function sumRows(dataset: CommerceDatasetDetail): number {
  return dataset.profile.tables.reduce(
    (total, table) => total + table.row_count,
    0,
  );
}

function tableRoleLabel(tableName: string): string {
  const normalized = tableName.toLowerCase();
  if (normalized.includes("review")) return "评价";
  if (normalized.includes("item")) return "订单明细";
  if (normalized.includes("product")) return "商品";
  if (normalized.includes("seller")) return "卖家";
  if (normalized.includes("customer")) return "客户";
  if (normalized.includes("order")) return "订单";
  return "数据表";
}

function semanticLabel(field: string): string {
  return SEMANTIC_LABELS[field] ?? "经营字段";
}

function semanticDetailLabel(field: string): string {
  return SEMANTIC_DETAIL_LABELS[field] ?? semanticLabel(field);
}
