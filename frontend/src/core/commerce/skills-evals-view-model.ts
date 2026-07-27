import type {
  CommerceSkillCandidate,
  CommerceSkillCandidateEvidence,
} from "./types";

export type CommerceSkillCandidateFilter =
  | "all"
  | "review"
  | "active"
  | "historical"
  | "failed";

export type CommerceSkillGateStatus =
  | "completed"
  | "current"
  | "blocked"
  | "not_started";

export interface CommerceSkillCandidateQueueItemViewModel {
  id: string;
  title: string;
  statusLabel: string;
  statusGroup: Exclude<CommerceSkillCandidateFilter, "all">;
  lineageLabel: string;
  timeLabel: string;
}

export interface CommerceSkillsEvalsViewModel {
  title: string;
  subtitle: string;
  filters: Array<{
    value: CommerceSkillCandidateFilter;
    label: string;
    count: number;
  }>;
  summary: Array<{
    label: string;
    valueLabel: string;
    tone: "neutral" | "success" | "warning";
  }>;
  items: CommerceSkillCandidateQueueItemViewModel[];
  selected: {
    id: string;
    skillName: string;
    title: string;
    statusLabel: string;
    statusGroup: Exclude<CommerceSkillCandidateFilter, "all">;
    baseVersionLabel: string;
    hashLabel: string;
    proposedByLabel: string;
    purpose: string;
    stages: Array<{
      key: string;
      title: string;
      status: CommerceSkillGateStatus;
      statusLabel: string;
    }>;
    experiment: {
      candidateVersionLabel: string;
      controlVersionLabel: string;
      decisionLabel: string;
      recommendationLabel: string;
      requestCountLabel: string;
      rows: Array<{
        label: string;
        candidateLabel: string;
        controlLabel: string;
      }>;
      caseLabels: string[];
      experimentIdLabel: string;
      reproductionLabel: string;
    } | null;
    shadow: {
      summaryLabel: string;
      telemetryBoundaryLabel: string;
      runRows: Array<{ id: string; shortId: string }>;
      sideEffectBoundary: string;
    };
    governanceRows: string[];
    activePointerLabel: string;
    reviewerLabel: string;
    rollbackReasonLabel: string | null;
    canPromote: boolean;
    canRollback: boolean;
    primaryActionLabel: string;
  } | null;
}

export function buildCommerceSkillsEvalsViewModel({
  candidates,
  selectedCandidateId,
  selectedEvidence,
}: {
  candidates: CommerceSkillCandidate[];
  selectedCandidateId?: string | null;
  selectedEvidence: CommerceSkillCandidateEvidence | null;
}): CommerceSkillsEvalsViewModel {
  const ordered = [...candidates].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  );
  const newestBySkill = new Map<string, string>();
  for (const candidate of ordered) {
    if (!newestBySkill.has(candidate.skill_name)) {
      newestBySkill.set(candidate.skill_name, candidate.id);
    }
  }
  const items = ordered.map((candidate) =>
    projectQueueItem(candidate, newestBySkill.get(candidate.skill_name)),
  );
  const activeId =
    selectedCandidateId && items.some((item) => item.id === selectedCandidateId)
      ? selectedCandidateId
      : items[0]?.id;
  const activeCandidate = ordered.find((item) => item.id === activeId) ?? null;
  const evidence =
    activeCandidate && selectedEvidence?.candidate.id === activeCandidate.id
      ? selectedEvidence
      : null;
  const pointer = evidence?.active_pointer ?? null;
  const report = evidence?.report ?? null;
  return {
    title: "治理技能演进",
    subtitle: "候选技能不会直接生效，必须经过冻结评测、影子运行和人工审查。",
    filters: [
      filterItem("all", "全部", items),
      filterItem("review", "待审查", items),
      filterItem("active", "已生效", items),
      filterItem("historical", "历史", items),
      filterItem("failed", "失败", items),
    ],
    summary: [
      {
        label: "当前生效",
        valueLabel: pointer
          ? pointer.candidate_id
            ? pointer.version
            : `已回退至 ${pointer.version}`
          : "未建立指针",
        tone: pointer ? "success" : "neutral",
      },
      {
        label: "待人工审查",
        valueLabel: String(
          candidates.filter(
            (item) => item.status === "shadow" && item.reviewer_id === null,
          ).length,
        ),
        tone: "warning",
      },
      {
        label: "冻结评测",
        valueLabel: report
          ? `${report.candidate.passed_count} / ${report.candidate.run_count}`
          : "未观察",
        tone:
          report?.candidate.hard_gate_failures === 0 ? "success" : "neutral",
      },
      {
        label: "影子运行",
        valueLabel: activeCandidate?.shadow_passed
          ? `${activeCandidate.shadow_live_run_ids.length} / 2`
          : "未观察",
        tone: activeCandidate?.shadow_passed ? "success" : "neutral",
      },
    ],
    items,
    selected: activeCandidate
      ? projectSelectedCandidate(
          activeCandidate,
          evidence,
          newestBySkill.get(activeCandidate.skill_name),
        )
      : null,
  };
}

export function filterCommerceSkillCandidateItems(
  items: readonly CommerceSkillCandidateQueueItemViewModel[],
  options: { filter: CommerceSkillCandidateFilter; query: string },
) {
  const query = options.query.trim().toLocaleLowerCase("zh-CN");
  return items.filter((item) => {
    if (options.filter !== "all" && item.statusGroup !== options.filter) {
      return false;
    }
    return (
      !query ||
      [item.title, item.statusLabel, item.lineageLabel]
        .join(" ")
        .toLocaleLowerCase("zh-CN")
        .includes(query)
    );
  });
}

function projectQueueItem(
  candidate: CommerceSkillCandidate,
  newestCandidateId: string | undefined,
): CommerceSkillCandidateQueueItemViewModel {
  const historicalShadow =
    candidate.status === "shadow" && candidate.id !== newestCandidateId;
  return {
    id: candidate.id,
    title: `${skillLabel(candidate.skill_name)} ${candidate.candidate_version}`,
    statusLabel: historicalShadow
      ? "历史影子"
      : candidateStatusLabel(candidate.status),
    statusGroup: historicalShadow
      ? "historical"
      : candidateStatusGroup(candidate.status),
    lineageLabel: `基于 ${candidate.base_version}`,
    timeLabel: formatDateTime(candidate.updated_at),
  };
}

function projectSelectedCandidate(
  candidate: CommerceSkillCandidate,
  evidence: CommerceSkillCandidateEvidence | null,
  newestCandidateId: string | undefined,
): NonNullable<CommerceSkillsEvalsViewModel["selected"]> {
  const queue = projectQueueItem(candidate, newestCandidateId);
  const report = evidence?.report ?? null;
  const definition = evidence?.definition ?? null;
  const pointer = evidence?.active_pointer ?? null;
  return {
    id: candidate.id,
    skillName: candidate.skill_name,
    title: queue.title,
    statusLabel: queue.statusLabel,
    statusGroup: queue.statusGroup,
    baseVersionLabel: `基于 ${candidate.base_version}`,
    hashLabel: shortHash(candidate.content_sha256),
    proposedByLabel: proposedByLabel(candidate.proposed_by),
    purpose: candidatePurpose(candidate.source_failure_codes),
    stages: candidateStages(candidate),
    experiment:
      report && definition
        ? projectExperiment(candidate, definition, report)
        : null,
    shadow: {
      summaryLabel:
        candidate.shadow_live_run_ids.length > 0
          ? `${candidate.shadow_live_run_ids.length} 条真实运行`
          : "尚无影子运行",
      telemetryBoundaryLabel: "请求遥测未由当前接口开放",
      runRows: candidate.shadow_live_run_ids.map((id) => ({
        id,
        shortId: shortId(id),
      })),
      sideEffectBoundary: "未修改案例、证据、行动或生效指针",
    },
    governanceRows: [
      "运行中智能体不能修改生效技能",
      "晋级必须由人工审查者提交",
      "回滚保留候选、实验和审查记录",
    ],
    activePointerLabel: pointer
      ? pointer.candidate_id
        ? `当前指向 ${pointer.version}`
        : `已回退至 ${pointer.version}`
      : "未建立生效指针",
    reviewerLabel: candidate.reviewer_id ?? "尚未人工审查",
    rollbackReasonLabel: candidate.rollback_reason,
    canPromote: candidate.status === "shadow",
    canRollback: candidate.status === "active",
    primaryActionLabel:
      candidate.status === "active" ? "回滚生效版本" : "人工批准并激活",
  };
}

function projectExperiment(
  candidate: CommerceSkillCandidate,
  definition: NonNullable<CommerceSkillCandidateEvidence["definition"]>,
  report: NonNullable<CommerceSkillCandidateEvidence["report"]>,
) {
  const tokenChange = percentChange(
    report.candidate.mean_total_tokens,
    report.control.mean_total_tokens,
  );
  const latencyChange = percentChange(
    report.candidate.mean_latency_ms,
    report.control.mean_latency_ms,
  );
  const qualityLabel =
    report.candidate.pass_rate > report.control.pass_rate
      ? "质量提升"
      : "质量持平";
  return {
    candidateVersionLabel: `候选 ${candidate.candidate_version}`,
    controlVersionLabel: `对照 ${candidate.base_version}`,
    decisionLabel: experimentDecisionLabel(report.decision),
    recommendationLabel: `${qualityLabel}，令牌 ${formatSignedPercent(tokenChange)}，延迟 ${formatSignedPercent(latencyChange)}`,
    requestCountLabel: `${new Set(report.provider_request_ids).size} 个唯一请求编号`,
    rows: [
      {
        label: "通过",
        candidateLabel: `${report.candidate.passed_count} / ${report.candidate.run_count}`,
        controlLabel: `${report.control.passed_count} / ${report.control.run_count}`,
      },
      {
        label: "硬门禁失败",
        candidateLabel: String(report.candidate.hard_gate_failures),
        controlLabel: String(report.control.hard_gate_failures),
      },
      {
        label: "平均令牌",
        candidateLabel: formatInteger(report.candidate.mean_total_tokens),
        controlLabel: formatInteger(report.control.mean_total_tokens),
      },
      {
        label: "平均延迟",
        candidateLabel: formatDuration(report.candidate.mean_latency_ms),
        controlLabel: formatDuration(report.control.mean_latency_ms),
      },
    ],
    caseLabels: definition.case_keys.map(caseLabel),
    experimentIdLabel: shortId(definition.id),
    reproductionLabel: "复现实验命令已持久化",
  };
}

function candidateStages(candidate: CommerceSkillCandidate) {
  const evaluated = [
    "offline_evaluated",
    "shadow",
    "active",
    "rolled_back",
  ].includes(candidate.status);
  return [
    gate("candidate", "候选提出", "completed"),
    gate(
      "security",
      "安全扫描",
      candidate.security_scan.passed ? "completed" : "blocked",
    ),
    gate(
      "offline",
      "离线评测",
      evaluated && candidate.regression_passed ? "completed" : "not_started",
    ),
    gate(
      "holdout",
      "留出集",
      candidate.holdout_passed ? "completed" : "not_started",
    ),
    gate(
      "shadow",
      "影子运行",
      candidate.shadow_passed ? "completed" : "not_started",
    ),
    gate(
      "review",
      "人工审查",
      candidate.reviewer_id
        ? "completed"
        : candidate.status === "shadow"
          ? "current"
          : "not_started",
    ),
    gate(
      "active",
      "生效",
      candidate.status === "active"
        ? "completed"
        : ["rejected", "rolled_back"].includes(candidate.status)
          ? "blocked"
          : "not_started",
    ),
  ];
}

function gate(key: string, title: string, status: CommerceSkillGateStatus) {
  return { key, title, status, statusLabel: gateStatusLabel(status) };
}

function filterItem(
  value: CommerceSkillCandidateFilter,
  label: string,
  items: readonly CommerceSkillCandidateQueueItemViewModel[],
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

function candidateStatusGroup(
  status: CommerceSkillCandidate["status"],
): Exclude<CommerceSkillCandidateFilter, "all"> {
  if (status === "shadow") return "review";
  if (status === "active") return "active";
  if (status === "rejected" || status === "rolled_back") return "failed";
  return "historical";
}

function candidateStatusLabel(status: CommerceSkillCandidate["status"]) {
  return {
    candidate: "候选待评测",
    offline_evaluated: "等待影子运行",
    shadow: "待人工审查",
    active: "已生效",
    rejected: "已拒绝",
    rolled_back: "已回滚",
  }[status];
}

function gateStatusLabel(status: CommerceSkillGateStatus) {
  return {
    completed: "已完成",
    current: "当前门禁",
    blocked: "已阻塞",
    not_started: "未开始",
  }[status];
}

function candidatePurpose(codes: string[]) {
  if (codes.includes("unsupported-action-threshold")) {
    return "修复模型自造行动阈值的问题，只允许引用服务端已配置策略。";
  }
  if (codes.includes("no-transit-causal-certainty")) {
    return "降低履约链路中的因果确定性表达，保留证据边界。";
  }
  return "针对已记录评测失败提出受控技能变更。";
}

function skillLabel(name: string) {
  return name === "commerce-diagnostic-synthesis" ? "诊断综合" : "技能候选";
}

function proposedByLabel(value: string) {
  return value === "skill-evolution-runner"
    ? "由评测流水线提出"
    : `由 ${value} 提出`;
}

function experimentDecisionLabel(value: string) {
  return (
    {
      promote_candidate: "建议晋级",
      hold: "暂缓晋级",
      reject_candidate: "拒绝候选",
    }[value] ?? "决策待确认"
  );
}

function caseLabel(value: string) {
  return (
    {
      "GC-FULFILLMENT-001": "履约",
      "GC-REVIEW-002": "评价",
      "GC-CAPABILITY-003": "能力边界",
      "GC-PEER-004": "卖家对标",
    }[value] ?? value
  );
}

function percentChange(candidate: number, control: number) {
  return control === 0 ? 0 : ((candidate - control) / control) * 100;
}

function formatSignedPercent(value: number) {
  const rounded = new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
  return `${value > 0 ? "+" : ""}${rounded}%`;
}

function formatInteger(value: number) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(
    value,
  );
}

function formatDuration(value: number) {
  return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(value / 1000)} 秒`;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function shortHash(value: string) {
  return `${value.slice(0, 4)}…${value.slice(-4)}`;
}

function shortId(value: string) {
  return value.length <= 16 ? value : `${value.slice(0, 7)}…${value.slice(-4)}`;
}
