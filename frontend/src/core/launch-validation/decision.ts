import type { Message } from "@langchain/langgraph-sdk";

import { textOfMessage } from "@/core/threads/utils";

export const VALIDATION_RESULT_MARKER = "OPENSKU_VALIDATION_RESULT_V1";

export type LaunchDecisionCode =
  | "test_now"
  | "test_after_fixing_assumptions"
  | "hold"
  | "insufficient_evidence";

export type EvidenceLabel =
  | "observed_public"
  | "uploaded_real"
  | "estimated"
  | "assumption"
  | "unavailable";

export type EvidenceState =
  | "insufficient"
  | "partial"
  | "supported"
  | "conflicting";

export type ValidationOutcome = "met" | "partial" | "not_met" | "inconclusive";

export interface LaunchEvidence {
  id: string;
  claim: string;
  evidenceLabel: EvidenceLabel;
  sourceUrls: string[];
  limitation: string;
  confidence: string;
}

export interface LaunchExperiment {
  day: string;
  action: string;
  evidenceToCollect: string;
  successCriterion: string;
  stopCondition: string;
}

export interface LaunchSpec {
  category: string;
  targetPrice: string;
  decision: LaunchDecisionCode;
  decisionRationale: string;
  audience: string;
  validationGoal: string;
  hypotheses: string[];
  experiments: LaunchExperiment[];
  evidence: LaunchEvidence[];
  messageIndex: number;
}

export interface ValidationResult {
  experiment: string;
  date: string;
  sampleDefinition: string;
  observation: string;
  outcome: ValidationOutcome;
  messageIndex: number;
}

export interface LaunchDecisionWorkspaceModel {
  initialSpec: LaunchSpec | null;
  currentSpec: LaunchSpec | null;
  evidence: LaunchEvidence[];
  evidenceState: EvidenceState;
  experiments: LaunchExperiment[];
  validationResults: ValidationResult[];
  decisionChanged: boolean;
  pendingReassessment: boolean;
}

type UnknownRecord = Record<string, unknown>;

const DECISION_CODES = new Set<LaunchDecisionCode>([
  "test_now",
  "test_after_fixing_assumptions",
  "hold",
  "insufficient_evidence",
]);

const EVIDENCE_LABELS = new Set<EvidenceLabel>([
  "observed_public",
  "uploaded_real",
  "estimated",
  "assumption",
  "unavailable",
]);

const VALIDATION_OUTCOMES = new Set<ValidationOutcome>([
  "met",
  "partial",
  "not_met",
  "inconclusive",
]);

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function stringList(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

function decisionCode(value: unknown): LaunchDecisionCode {
  const normalized = text(value).toLowerCase() as LaunchDecisionCode;
  return DECISION_CODES.has(normalized) ? normalized : "insufficient_evidence";
}

function evidenceLabel(value: unknown): EvidenceLabel {
  const normalized = text(value).toLowerCase() as EvidenceLabel;
  return EVIDENCE_LABELS.has(normalized) ? normalized : "assumption";
}

function normalizeEvidenceEntry(
  value: unknown,
  index: number,
): LaunchEvidence | null {
  if (!isRecord(value)) {
    return null;
  }
  const claim = text(value.claim ?? value.signal ?? value.finding);
  if (!claim) {
    return null;
  }
  const sourceValue = value.source_urls ?? value.source_url;
  const sourceUrls = Array.isArray(sourceValue)
    ? stringList(sourceValue)
    : text(sourceValue)
      ? [text(sourceValue)]
      : [];
  return {
    id: text(value.id, `E${index + 1}`),
    claim,
    evidenceLabel: evidenceLabel(value.evidence_label ?? value.label),
    sourceUrls,
    limitation: text(value.limitation ?? value.notes),
    confidence: text(value.confidence),
  };
}

function normalizeEvidence(value: unknown): LaunchEvidence[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(normalizeEvidenceEntry)
    .filter((entry): entry is LaunchEvidence => entry !== null);
}

function normalizeExperiment(
  value: unknown,
  index: number,
): LaunchExperiment | null {
  if (typeof value === "string") {
    const action = value.trim();
    return action
      ? {
          day: String(index + 1),
          action,
          evidenceToCollect: "",
          successCriterion: "",
          stopCondition: "",
        }
      : null;
  }
  if (!isRecord(value)) {
    return null;
  }
  const action = text(value.action ?? value.experiment);
  if (!action) {
    return null;
  }
  return {
    day: text(value.day, String(index + 1)),
    action,
    evidenceToCollect: text(
      value.evidence_to_collect ?? value.evidenceToCollect ?? value.signal,
    ),
    successCriterion: text(
      value.success_criterion ?? value.successCriterion ?? value.success,
    ),
    stopCondition: text(
      value.stop_condition ?? value.stopCondition ?? value.stop,
    ),
  };
}

function normalizeExperiments(value: unknown): LaunchExperiment[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(normalizeExperiment)
    .filter((entry): entry is LaunchExperiment => entry !== null);
}

function normalizeSpec(
  value: unknown,
  messageIndex: number,
): LaunchSpec | null {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed) as unknown;
    } catch {
      return null;
    }
  }
  if (!isRecord(parsed)) {
    return null;
  }
  const category = text(parsed.category ?? parsed.product_category);
  if (!category) {
    return null;
  }
  return {
    category,
    targetPrice: text(parsed.target_price ?? parsed.price_range),
    decision: decisionCode(parsed.decision ?? parsed.verdict),
    decisionRationale: text(parsed.decision_rationale ?? parsed.rationale),
    audience: text(parsed.audience ?? parsed.audience_wedge),
    validationGoal: text(parsed.validation_goal ?? parsed.goal),
    hypotheses: stringList(parsed.hypotheses),
    experiments: normalizeExperiments(parsed.experiments),
    evidence: normalizeEvidence(parsed.evidence),
    messageIndex,
  };
}

export function extractLaunchSpecs(messages: Message[]): LaunchSpec[] {
  const specs: LaunchSpec[] = [];
  const completedRenderCalls = new Set<string>();
  for (const message of messages) {
    if (message.type !== "tool" || typeof message.tool_call_id !== "string") {
      continue;
    }
    const result = textOfMessage(message)?.trim() ?? "";
    const failed =
      /^(?:error|failed|preflight failed|validation failed)\b/i.test(result);
    if (!failed && result) {
      completedRenderCalls.add(message.tool_call_id);
    }
  }
  messages.forEach((message, messageIndex) => {
    if (message.type !== "ai") {
      return;
    }
    for (const toolCall of message.tool_calls ?? []) {
      if (toolCall.name !== "render_launch_pack") {
        continue;
      }
      if (!toolCall.id || !completedRenderCalls.has(toolCall.id)) {
        continue;
      }
      const args = toolCall.args;
      const specValue = isRecord(args) ? args.spec : undefined;
      const spec = normalizeSpec(specValue, messageIndex);
      if (spec) {
        specs.push(spec);
      }
    }
  });
  return specs;
}

export function parseEvidenceLedger(content: string | undefined) {
  if (!content?.trim()) {
    return [];
  }
  try {
    const parsed = JSON.parse(content) as unknown;
    if (Array.isArray(parsed)) {
      return normalizeEvidence(parsed);
    }
    return isRecord(parsed) ? normalizeEvidence(parsed.entries) : [];
  } catch {
    return [];
  }
}

function parseCsvRows(content: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index]!;
    if (quoted) {
      if (char === '"' && content[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field.trim());
      field = "";
    } else if (char === "\n") {
      row.push(field.trim());
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field || row.length > 0) {
    row.push(field.trim());
    rows.push(row);
  }
  return rows.filter((values) => values.some(Boolean));
}

export function parseLaunchCalendar(content: string | undefined) {
  if (!content?.trim()) {
    return [];
  }
  const [headers, ...rows] = parseCsvRows(content);
  if (!headers) {
    return [];
  }
  const headerIndex = new Map(headers.map((header, index) => [header, index]));
  if (!headerIndex.has("action")) {
    return [];
  }
  const cell = (row: string[], name: string) => {
    const index = headerIndex.get(name);
    return index === undefined ? "" : (row[index] ?? "");
  };
  return rows
    .map((row, index) =>
      normalizeExperiment(
        {
          day: cell(row, "day") || String(index + 1),
          action: cell(row, "action"),
          evidence_to_collect: cell(row, "evidence_to_collect"),
          success_criterion: cell(row, "success_criterion"),
          stop_condition: cell(row, "stop_condition"),
        },
        index,
      ),
    )
    .filter((entry): entry is LaunchExperiment => entry !== null);
}

export function formatValidationResultMessage(
  result: Omit<ValidationResult, "messageIndex">,
  language: "zh" | "en",
) {
  const payload = JSON.stringify(result, null, 2);
  const instruction =
    language === "zh"
      ? "请记录并分析这条真实验证结果，重新检查证据状态、关键假设和停止条件。如结论需要变化，请用新的 render_launch_pack 结果明确更新当前 Launch 决策；不要覆盖未经证实的事实。"
      : "Record and analyze this real validation result. Reassess the evidence state, critical assumptions, and stop conditions. If the conclusion should change, explicitly update the current Launch decision with a new render_launch_pack result; do not overwrite unverified facts.";
  return `[${VALIDATION_RESULT_MARKER}]\n\n\`\`\`json\n${payload}\n\`\`\`\n\n${instruction}`;
}

export function parseValidationResults(messages: Message[]) {
  const results: ValidationResult[] = [];
  messages.forEach((message, messageIndex) => {
    if (message.type !== "human") {
      return;
    }
    const content = textOfMessage(message);
    if (!content?.includes(`[${VALIDATION_RESULT_MARKER}]`)) {
      return;
    }
    const jsonMatch = /```json\s*([\s\S]*?)\s*```/i.exec(content);
    if (!jsonMatch?.[1]) {
      return;
    }
    try {
      const parsed = JSON.parse(jsonMatch[1]) as unknown;
      if (!isRecord(parsed)) {
        return;
      }
      const experiment = text(parsed.experiment);
      const observation = text(parsed.observation);
      const outcome = text(parsed.outcome) as ValidationOutcome;
      if (!experiment || !observation || !VALIDATION_OUTCOMES.has(outcome)) {
        return;
      }
      results.push({
        experiment,
        date: text(parsed.date),
        sampleDefinition: text(parsed.sampleDefinition),
        observation,
        outcome,
        messageIndex,
      });
    } catch {
      return;
    }
  });
  return results;
}

export function getEvidenceState(
  evidence: LaunchEvidence[],
  results: ValidationResult[],
): EvidenceState {
  const outcomes = new Set(results.map((result) => result.outcome));
  if (outcomes.has("met") && outcomes.has("not_met")) {
    return "conflicting";
  }
  const verified = evidence.filter((entry) =>
    ["observed_public", "uploaded_real"].includes(entry.evidenceLabel),
  ).length;
  if (verified === 0) {
    return results.some((result) => result.outcome === "met")
      ? "partial"
      : "insufficient";
  }
  const weak = evidence.length - verified;
  return weak === 0 && results.every((result) => result.outcome !== "not_met")
    ? "supported"
    : "partial";
}

export function buildDecisionWorkspaceModel({
  messages,
  evidenceLedger,
  launchCalendar,
}: {
  messages: Message[];
  evidenceLedger?: string;
  launchCalendar?: string;
}): LaunchDecisionWorkspaceModel {
  const specs = extractLaunchSpecs(messages);
  const initialSpec = specs[0] ?? null;
  const currentSpec = specs.at(-1) ?? null;
  const ledgerEvidence = parseEvidenceLedger(evidenceLedger);
  const evidence = ledgerEvidence.length
    ? ledgerEvidence
    : (currentSpec?.evidence ?? []);
  const calendarExperiments = parseLaunchCalendar(launchCalendar);
  const experiments = calendarExperiments.length
    ? calendarExperiments
    : (currentSpec?.experiments ?? []);
  const validationResults = parseValidationResults(messages);
  const latestResultIndex = validationResults.at(-1)?.messageIndex ?? -1;
  const latestDecisionIndex = currentSpec?.messageIndex ?? -1;
  return {
    initialSpec,
    currentSpec,
    evidence,
    evidenceState: getEvidenceState(evidence, validationResults),
    experiments,
    validationResults,
    decisionChanged:
      initialSpec !== null &&
      currentSpec !== null &&
      initialSpec.decision !== currentSpec.decision,
    pendingReassessment: latestResultIndex > latestDecisionIndex,
  };
}

export function buildGrowthAnalystHandoff(
  model: LaunchDecisionWorkspaceModel,
  language: "zh" | "en",
) {
  const spec = model.currentSpec;
  if (!spec) {
    return "";
  }
  const context = {
    source: "OpenSKU Launch Team",
    category: spec.category,
    currentDecision: spec.decision,
    decisionRationale: spec.decisionRationale,
    validationGoal: spec.validationGoal,
    hypotheses: spec.hypotheses,
    experiments: model.experiments,
    recordedResults: model.validationResults.map(
      ({ messageIndex: _, ...result }) => result,
    ),
  };
  const instruction =
    language === "zh"
      ? "这是 OpenSKU 上新团队的显式交接。请先让我上传 CSV/XLSX 验证数据，再只基于上传数据分析实验结果、样本口径和异常。输出可回传给 Launch Team 的结论、限制和建议决策；不要把相关性写成因果。"
      : "This is an explicit handoff from the OpenSKU Launch Team. Ask me to upload the CSV/XLSX validation data first, then analyze experiment outcomes, sample definitions, and anomalies using only the uploaded data. Return conclusions, limitations, and a proposed decision for the Launch Team without treating correlation as causation.";
  return `[OPENSKU_GROWTH_HANDOFF_V1]\n\n\`\`\`json\n${JSON.stringify(context, null, 2)}\n\`\`\`\n\n${instruction}`;
}

export function buildLaunchUpdateFromGrowth(
  growthAnalysis: string,
  language: "zh" | "en",
) {
  const instruction =
    language === "zh"
      ? "这是 Growth Analyst 的显式回传。请把它作为新证据审查，而不是自动采纳；核对样本口径与限制后，明确更新或维持当前 Launch 决策，并在需要时重新生成 render_launch_pack。"
      : "This is an explicit return from Growth Analyst. Review it as new evidence rather than accepting it automatically. Check the sample definition and limitations, then explicitly update or retain the current Launch decision and regenerate render_launch_pack when needed.";
  return `[OPENSKU_GROWTH_RETURN_V1]\n\n${growthAnalysis.trim()}\n\n${instruction}`;
}
