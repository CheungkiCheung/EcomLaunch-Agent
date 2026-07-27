"use client";

import {
  BadgeCheckIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleAlertIcon,
  FileSearchIcon,
  FlaskConicalIcon,
  GitCompareArrowsIcon,
  LoaderCircleIcon,
  LockKeyholeIcon,
  RotateCcwIcon,
  SearchIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserCheckIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildCommerceSkillsEvalsViewModel,
  CommerceApiError,
  filterCommerceSkillCandidateItems,
  loadCommerceSkillsEvalsSnapshot,
  promoteCommerceSkillCandidate,
  rollbackCommerceActiveSkill,
  type CommerceSkillCandidateFilter,
  type CommerceSkillGateStatus,
  type CommerceSkillsEvalsSnapshot,
  type CommerceSkillsEvalsViewModel,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

export function CommerceSkillsEvals({
  workspaceId,
  actorId,
  refreshSignal = 0,
}: {
  workspaceId: string | null;
  actorId: string | null;
  refreshSignal?: number;
}) {
  const [snapshot, setSnapshot] = useState<CommerceSkillsEvalsSnapshot | null>(
    null,
  );
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(
    null,
  );
  const [filter, setFilter] = useState<CommerceSkillCandidateFilter>("all");
  const [query, setQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rollbackReason, setRollbackReason] = useState("");
  const [showExperimentEvidence, setShowExperimentEvidence] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    void loadCommerceSkillsEvalsSnapshot({
      workspaceId: workspaceId ?? "",
      selectedCandidateId: selectedCandidateId ?? undefined,
      signal: controller.signal,
    })
      .then((result) => {
        setSnapshot(result);
        setSelectedCandidateId(
          result.selectedEvidence?.candidate.id ??
            result.candidates[0]?.id ??
            null,
        );
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") {
          return;
        }
        setError(skillsErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [refreshSignal, reloadKey, selectedCandidateId, workspaceId]);

  const viewModel = useMemo(
    () =>
      buildCommerceSkillsEvalsViewModel({
        candidates: snapshot?.candidates ?? [],
        selectedCandidateId,
        selectedEvidence: snapshot?.selectedEvidence ?? null,
      }),
    [selectedCandidateId, snapshot],
  );

  const submitPrimaryAction = async () => {
    const selected = viewModel.selected;
    if (!selected || !workspaceId || !actorId || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      if (selected.canPromote) {
        const result = await promoteCommerceSkillCandidate({
          workspaceId,
          actorId,
          candidateId: selected.id,
          idempotencyKey: `promote-${selected.id}`,
        });
        setNotice(
          result.replayed
            ? "已读取同一人工晋级请求的既有结果。"
            : `候选版本 ${result.candidate.candidate_version} 已由人工审查者激活。`,
        );
      } else if (selected.canRollback) {
        if (!rollbackReason.trim()) {
          setError("回滚必须填写原因，当前没有执行任何操作。");
          return;
        }
        const result = await rollbackCommerceActiveSkill({
          workspaceId,
          actorId,
          skillName: selected.skillName,
          reason: rollbackReason,
          idempotencyKey: `rollback-${selected.id}`,
        });
        setNotice(
          result.replayed
            ? "已读取同一回滚请求的既有结果。"
            : `生效指针已回退至 ${result.active_pointer.version}，候选与实验记录保持不可变。`,
        );
        setRollbackReason("");
      }
      setReloadKey((value) => value + 1);
    } catch (cause) {
      setError(skillsErrorMessage(cause));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <CommerceSkillsEvalsView
      viewModel={viewModel}
      filter={filter}
      query={query}
      isLoading={isLoading}
      isSubmitting={isSubmitting}
      actorAvailable={Boolean(actorId?.trim())}
      notice={notice}
      error={error}
      rollbackReason={rollbackReason}
      showExperimentEvidence={showExperimentEvidence}
      onFilterChange={setFilter}
      onQueryChange={setQuery}
      onSelectCandidate={(candidateId) => {
        setSelectedCandidateId(candidateId);
        setNotice(null);
        setError(null);
        setRollbackReason("");
        setShowExperimentEvidence(false);
      }}
      onRollbackReasonChange={setRollbackReason}
      onPrimaryAction={submitPrimaryAction}
      onToggleExperimentEvidence={() =>
        setShowExperimentEvidence((value) => !value)
      }
    />
  );
}

export function CommerceSkillsEvalsView({
  viewModel,
  filter,
  query,
  isLoading,
  isSubmitting,
  actorAvailable,
  notice,
  error,
  rollbackReason,
  showExperimentEvidence,
  onFilterChange,
  onQueryChange,
  onSelectCandidate,
  onRollbackReasonChange,
  onPrimaryAction,
  onToggleExperimentEvidence,
}: {
  viewModel: CommerceSkillsEvalsViewModel;
  filter: CommerceSkillCandidateFilter;
  query: string;
  isLoading: boolean;
  isSubmitting: boolean;
  actorAvailable: boolean;
  notice: string | null;
  error: string | null;
  rollbackReason: string;
  showExperimentEvidence: boolean;
  onFilterChange: (value: CommerceSkillCandidateFilter) => void;
  onQueryChange: (value: string) => void;
  onSelectCandidate: (candidateId: string) => void;
  onRollbackReasonChange: (value: string) => void;
  onPrimaryAction: () => void;
  onToggleExperimentEvidence: () => void;
}) {
  const items = useMemo(
    () => filterCommerceSkillCandidateItems(viewModel.items, { filter, query }),
    [filter, query, viewModel.items],
  );
  const selected = viewModel.selected;

  return (
    <section
      className="mx-auto w-full max-w-[1240px] px-5 py-7 sm:px-8 lg:px-9"
      data-testid="commerce-skills-evals"
    >
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.03em] text-[#292925]">
          {viewModel.title}
        </h1>
        <p className="mt-2 max-w-[780px] text-sm leading-6 text-[#6f6f69]">
          {viewModel.subtitle}
        </p>
      </div>

      <div className="mt-5 grid grid-cols-2 overflow-hidden rounded-2xl border border-black/[0.08] bg-white xl:grid-cols-4">
        {viewModel.summary.map((item) => (
          <SummaryCard key={item.label} item={item} />
        ))}
      </div>

      <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex gap-2 overflow-x-auto pb-1 xl:pb-0">
          {viewModel.filters.map((item) => (
            <button
              type="button"
              key={item.value}
              aria-pressed={filter === item.value}
              className={cn(
                "min-h-9 shrink-0 rounded-lg border px-3 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2",
                item.count === 0 && "hidden sm:block",
                filter === item.value
                  ? "border-[#292926] bg-[#292926] text-white"
                  : "border-black/[0.08] bg-[#fafaf8] text-[#61615b] hover:bg-black/[0.04]",
              )}
              onClick={() => onFilterChange(item.value)}
            >
              {item.label}
              <span className="ml-1.5 opacity-70">{item.count}</span>
            </button>
          ))}
        </div>
        <label className="flex min-h-10 w-full items-center gap-2 rounded-lg border border-black/[0.09] bg-white px-3 xl:w-[280px]">
          <SearchIcon className="size-4 text-[#777771]" aria-hidden="true" />
          <span className="sr-only">搜索候选版本</span>
          <input
            type="search"
            value={query}
            placeholder="搜索候选版本"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#9a9a94]"
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      {notice && <Notice tone="success">{notice}</Notice>}

      {isLoading && viewModel.items.length === 0 ? (
        <div className="mt-8 flex min-h-[38vh] items-center justify-center text-sm text-[#74746e]">
          <LoaderCircleIcon
            className="mr-2 size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          正在读取技能候选与评测依据
        </div>
      ) : viewModel.items.length === 0 ? (
        <SkillsEmptyState />
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <CandidateQueue
            items={items}
            selected={selected}
            onSelectCandidate={onSelectCandidate}
          />
          {selected ? (
            <CandidateDocument
              selected={selected}
              actorAvailable={actorAvailable}
              isSubmitting={isSubmitting}
              rollbackReason={rollbackReason}
              showExperimentEvidence={showExperimentEvidence}
              onRollbackReasonChange={onRollbackReasonChange}
              onPrimaryAction={onPrimaryAction}
              onToggleExperimentEvidence={onToggleExperimentEvidence}
            />
          ) : (
            <FilteredEmptyState />
          )}
        </div>
      )}
    </section>
  );
}

function SummaryCard({
  item,
}: {
  item: CommerceSkillsEvalsViewModel["summary"][number];
}) {
  const Icon =
    item.label === "当前生效"
      ? BadgeCheckIcon
      : item.label === "待人工审查"
        ? UserCheckIcon
        : item.label === "冻结评测"
          ? FlaskConicalIcon
          : SparklesIcon;
  return (
    <div className="flex min-h-24 items-center gap-3 border-r border-b border-black/[0.07] px-4 py-4 last:border-r-0 sm:px-5 xl:border-b-0">
      <span
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-xl border",
          item.tone === "success" &&
            "border-emerald-200 bg-emerald-50 text-emerald-700",
          item.tone === "warning" &&
            "border-amber-200 bg-amber-50 text-amber-700",
          item.tone === "neutral" &&
            "border-black/[0.08] bg-[#fafaf8] text-[#666660]",
        )}
      >
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[#393934]">{item.label}</p>
        <p className="mt-1 truncate text-xs text-[#666660]">
          {item.valueLabel}
        </p>
      </div>
    </div>
  );
}

function CandidateQueue({
  items,
  selected,
  onSelectCandidate,
}: {
  items: CommerceSkillsEvalsViewModel["items"];
  selected: CommerceSkillsEvalsViewModel["selected"];
  onSelectCandidate: (candidateId: string) => void;
}) {
  return (
    <div>
      {selected && (
        <div className="relative rounded-xl border border-black/[0.09] bg-white p-4 xl:hidden">
          <select
            aria-label="切换候选版本"
            value={selected.id}
            className="absolute inset-0 z-10 size-full cursor-pointer appearance-none opacity-0"
            onChange={(event) => onSelectCandidate(event.target.value)}
          >
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} · {item.statusLabel}
              </option>
            ))}
          </select>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-[#353531]">
                  {selected.title}
                </p>
                <CandidateStatusChip group={selected.statusGroup}>
                  {selected.statusLabel}
                </CandidateStatusChip>
              </div>
              <p className="mt-2 text-xs text-[#6f6f69]">
                {selected.baseVersionLabel} · 内容哈希 {selected.hashLabel}
              </p>
            </div>
            <ChevronDownIcon
              className="mt-0.5 size-4 shrink-0 text-[#777771]"
              aria-hidden="true"
            />
          </div>
          <p className="mt-4 border-t border-black/[0.06] pt-3 text-center text-xs text-[#666660]">
            切换候选版本 {items.length}
          </p>
        </div>
      )}

      <div className="hidden xl:block">
        <h2 className="mb-3 text-sm font-semibold text-[#393934]">候选版本</h2>
        <div className="space-y-2" aria-label="候选版本队列">
          {items.map((item) => (
            <button
              type="button"
              key={item.id}
              aria-current={item.id === selected?.id ? "true" : undefined}
              className={cn(
                "w-full rounded-xl border px-4 py-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2",
                item.id === selected?.id
                  ? "border-amber-400 bg-amber-50/25"
                  : "border-black/[0.08] bg-white hover:bg-[#fafaf8]",
              )}
              onClick={() => onSelectCandidate(item.id)}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-[#383834]">
                  {item.title}
                </p>
                <CandidateStatusChip group={item.statusGroup}>
                  {item.statusLabel}
                </CandidateStatusChip>
              </div>
              <p className="mt-3 text-xs text-[#6f6f69]">
                {item.lineageLabel} · {item.timeLabel}
              </p>
            </button>
          ))}
          {items.length === 0 && <FilteredEmptyState />}
        </div>
      </div>
    </div>
  );
}

function CandidateDocument({
  selected,
  actorAvailable,
  isSubmitting,
  rollbackReason,
  showExperimentEvidence,
  onRollbackReasonChange,
  onPrimaryAction,
  onToggleExperimentEvidence,
}: {
  selected: NonNullable<CommerceSkillsEvalsViewModel["selected"]>;
  actorAvailable: boolean;
  isSubmitting: boolean;
  rollbackReason: string;
  showExperimentEvidence: boolean;
  onRollbackReasonChange: (value: string) => void;
  onPrimaryAction: () => void;
  onToggleExperimentEvidence: () => void;
}) {
  return (
    <article className="min-w-0 overflow-hidden rounded-2xl border border-black/[0.09] bg-white shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
      <header className="px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-semibold tracking-[-0.02em] text-[#2e2e2a]">
            {selected.title}
          </h2>
          <CandidateStatusChip group={selected.statusGroup}>
            {selected.statusLabel}
          </CandidateStatusChip>
          <span className="rounded-md border border-black/[0.08] bg-[#fafaf8] px-2 py-1 text-[10px] font-medium text-[#6f6f69]">
            候选版本
          </span>
        </div>
        <p className="mt-2 text-xs text-[#777771]">
          {selected.baseVersionLabel} · 内容哈希 {selected.hashLabel} ·{" "}
          {selected.proposedByLabel}
        </p>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[#555550]">
          {selected.purpose}
        </p>
      </header>

      <DocumentSection title="演进门禁">
        <EvolutionPipeline stages={selected.stages} />
      </DocumentSection>

      <div className="lg:grid lg:grid-cols-[minmax(0,1.12fr)_minmax(300px,0.88fr)]">
        <DocumentSection title="冻结实验对比" border sideBorder={false}>
          {selected.experiment ? (
            <ExperimentComparison experiment={selected.experiment} />
          ) : (
            <UnobservedState>冻结实验依据未观察</UnobservedState>
          )}
        </DocumentSection>
        <DocumentSection title="影子运行" border sideBorder>
          <ShadowRuns shadow={selected.shadow} />
        </DocumentSection>
      </div>

      <DocumentSection title="治理边界">
        <div className="grid gap-3 md:grid-cols-3">
          {selected.governanceRows.map((row) => (
            <div
              key={row}
              className="flex items-start gap-2 text-xs leading-5 text-[#555550]"
            >
              <CheckCircle2Icon
                className="mt-0.5 size-4 shrink-0 text-emerald-700"
                aria-hidden="true"
              />
              <span>{row}</span>
            </div>
          ))}
        </div>
      </DocumentSection>

      {showExperimentEvidence && selected.experiment && (
        <DocumentSection title="实验依据">
          <dl className="grid gap-3 rounded-xl border border-black/[0.08] bg-[#fafaf8] px-4 py-4 text-xs sm:grid-cols-3">
            <EvidenceDatum
              label="实验编号"
              value={selected.experiment.experimentIdLabel}
            />
            <EvidenceDatum
              label="模型请求"
              value={selected.experiment.requestCountLabel}
            />
            <EvidenceDatum
              label="复现边界"
              value={selected.experiment.reproductionLabel}
            />
          </dl>
        </DocumentSection>
      )}

      <section className="border-t border-black/[0.07] bg-[#fcfcfa] px-5 py-5 sm:px-6">
        {selected.canRollback && (
          <label className="mb-4 block">
            <span className="text-xs font-medium text-[#555550]">回滚原因</span>
            <textarea
              value={rollbackReason}
              rows={3}
              placeholder="说明为什么需要回退当前生效版本"
              className="mt-2 w-full resize-y rounded-xl border border-black/[0.09] bg-white px-3 py-2.5 text-sm outline-none focus:border-black/30"
              onChange={(event) => onRollbackReasonChange(event.target.value)}
            />
          </label>
        )}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            aria-expanded={showExperimentEvidence}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-black/[0.11] bg-white px-4 text-xs font-medium text-[#4e4e49] hover:bg-black/[0.03] focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={onToggleExperimentEvidence}
          >
            <FileSearchIcon className="size-4" aria-hidden="true" />
            {showExperimentEvidence ? "收起实验依据" : "查看实验依据"}
          </button>
          {(selected.canPromote || selected.canRollback) && (
            <button
              type="button"
              disabled={!actorAvailable || isSubmitting}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-[#292926] px-4 text-xs font-medium text-white hover:bg-[#1f1f1d] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-45"
              onClick={onPrimaryAction}
            >
              {isSubmitting ? (
                <LoaderCircleIcon
                  className="size-4 animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
              ) : selected.canRollback ? (
                <RotateCcwIcon className="size-4" aria-hidden="true" />
              ) : (
                <UserCheckIcon className="size-4" aria-hidden="true" />
              )}
              {selected.primaryActionLabel}
            </button>
          )}
          <div className="sm:ml-auto">
            <p className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900">
              <LockKeyholeIcon className="size-3.5" aria-hidden="true" />
              {actorAvailable
                ? `${selected.activePointerLabel} · ${selected.reviewerLabel}`
                : "当前操作需要审查者身份"}
            </p>
          </div>
        </div>
        {selected.rollbackReasonLabel && (
          <p className="mt-3 text-xs leading-5 text-[#666660]">
            最近回滚原因：{selected.rollbackReasonLabel}
          </p>
        )}
      </section>
    </article>
  );
}

function EvolutionPipeline({
  stages,
}: {
  stages: NonNullable<CommerceSkillsEvalsViewModel["selected"]>["stages"];
}) {
  return (
    <>
      <ol className="hidden grid-cols-7 md:grid">
        {stages.map((stage, index) => (
          <li key={stage.key} className="relative text-center">
            {index > 0 && (
              <span
                className={cn(
                  "absolute top-4 right-1/2 h-px w-full",
                  stage.status === "completed"
                    ? "bg-emerald-600"
                    : stage.status === "current"
                      ? "bg-amber-400"
                      : "border-t border-dashed border-black/20",
                )}
              />
            )}
            <GateMarker index={index} status={stage.status} />
            <p className="relative mt-2 text-[11px] font-medium text-[#4f4f4a]">
              {stage.title}
            </p>
          </li>
        ))}
      </ol>
      <ol className="space-y-0 md:hidden">
        {stages.map((stage, index) => (
          <li
            key={stage.key}
            className="relative flex items-center gap-3 pb-4 last:pb-0"
          >
            {index < stages.length - 1 && (
              <span className="absolute top-7 bottom-0 left-3 w-px bg-black/[0.09]" />
            )}
            <GateMarker index={index} status={stage.status} />
            <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
              <p className="text-sm font-medium text-[#44443f]">
                {stage.title}
              </p>
              <span className="text-[10px] text-[#777771]">
                {stage.statusLabel}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}

function GateMarker({
  index,
  status,
}: {
  index: number;
  status: CommerceSkillGateStatus;
}) {
  return (
    <span
      className={cn(
        "relative z-[1] mx-auto flex size-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
        status === "completed" &&
          "border-emerald-700 bg-emerald-700 text-white",
        status === "current" && "border-amber-500 bg-amber-50 text-amber-800",
        status === "blocked" && "border-red-500 bg-red-50 text-red-700",
        status === "not_started" &&
          "border-black/[0.13] bg-white text-[#777771]",
      )}
    >
      {status === "completed" ? (
        <CheckCircle2Icon className="size-4" aria-hidden="true" />
      ) : status === "blocked" ? (
        <XCircleIcon className="size-4" aria-hidden="true" />
      ) : (
        index + 1
      )}
    </span>
  );
}

function ExperimentComparison({
  experiment,
}: {
  experiment: NonNullable<
    NonNullable<CommerceSkillsEvalsViewModel["selected"]>["experiment"]
  >;
}) {
  return (
    <div>
      <div className="overflow-hidden rounded-xl border border-black/[0.08] bg-white text-xs">
        <div className="grid grid-cols-[minmax(90px,1fr)_1fr_1fr] border-b border-black/[0.07] bg-[#fafaf8] text-center font-medium text-[#555550]">
          <div className="px-3 py-3 text-left">指标</div>
          <div className="border-l border-black/[0.06] px-3 py-3 text-emerald-700">
            {experiment.candidateVersionLabel}
          </div>
          <div className="border-l border-black/[0.06] px-3 py-3">
            {experiment.controlVersionLabel}
          </div>
        </div>
        {experiment.rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-[minmax(90px,1fr)_1fr_1fr] border-b border-black/[0.06] last:border-b-0"
          >
            <div className="px-3 py-3 font-medium text-[#555550]">
              {row.label}
            </div>
            <div className="border-l border-black/[0.06] px-3 py-3 text-center font-medium text-emerald-700 tabular-nums">
              {row.candidateLabel}
            </div>
            <div className="border-l border-black/[0.06] px-3 py-3 text-center text-[#555550] tabular-nums">
              {row.controlLabel}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs leading-5 text-emerald-900">
        <p className="font-medium">{experiment.decisionLabel}</p>
        <p className="mt-0.5">{experiment.recommendationLabel}</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {experiment.caseLabels.map((label) => (
          <span
            key={label}
            className="rounded-lg border border-black/[0.08] bg-[#fafaf8] px-2.5 py-1.5 text-[11px] text-[#5f5f59]"
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function ShadowRuns({
  shadow,
}: {
  shadow: NonNullable<CommerceSkillsEvalsViewModel["selected"]>["shadow"];
}) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-emerald-800">
          {shadow.summaryLabel}
        </span>
        <span className="text-[#777771]">·</span>
        <span className="text-[#777771]">{shadow.telemetryBoundaryLabel}</span>
      </div>
      {shadow.runRows.length > 0 ? (
        <div className="mt-3 overflow-hidden rounded-xl border border-black/[0.08] bg-white">
          {shadow.runRows.map((run) => (
            <div
              key={run.id}
              className="flex items-center justify-between gap-3 border-b border-black/[0.06] px-3 py-3 text-xs last:border-b-0"
            >
              <span className="font-mono text-[11px] text-[#555550]">
                {run.shortId}
              </span>
              <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-700">
                完成
              </span>
            </div>
          ))}
        </div>
      ) : (
        <UnobservedState>影子运行未观察</UnobservedState>
      )}
      <p className="mt-3 flex items-start gap-2 text-[11px] leading-5 text-[#666660]">
        <ShieldCheckIcon
          className="mt-0.5 size-3.5 shrink-0 text-emerald-700"
          aria-hidden="true"
        />
        {shadow.sideEffectBoundary}
      </p>
    </div>
  );
}

function CandidateStatusChip({
  group,
  children,
}: {
  group: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-md border px-2 py-1 text-[10px] font-medium whitespace-nowrap",
        group === "review" && "border-amber-200 bg-amber-50 text-amber-700",
        group === "active" &&
          "border-emerald-200 bg-emerald-50 text-emerald-700",
        group === "failed" && "border-red-200 bg-red-50 text-red-700",
        group === "historical" &&
          "border-black/[0.08] bg-[#fafaf8] text-[#6f6f69]",
      )}
    >
      {children}
    </span>
  );
}

function DocumentSection({
  title,
  children,
  border = true,
  sideBorder = false,
}: {
  title: string;
  children: React.ReactNode;
  border?: boolean;
  sideBorder?: boolean;
}) {
  return (
    <section
      className={cn(
        "px-5 py-5 sm:px-6",
        border && "border-t border-black/[0.07]",
        sideBorder && "lg:border-l",
      )}
    >
      <h3 className="mb-4 text-sm font-semibold text-[#33332f]">{title}</h3>
      {children}
    </section>
  );
}

function EvidenceDatum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] text-[#777771]">{label}</dt>
      <dd className="mt-1 font-medium text-[#4f4f4a]">{value}</dd>
    </div>
  );
}

function Notice({
  tone,
  children,
}: {
  tone: "error" | "success";
  children: React.ReactNode;
}) {
  const Icon = tone === "error" ? CircleAlertIcon : CheckCircle2Icon;
  return (
    <div
      className={cn(
        "mt-4 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm",
        tone === "error"
          ? "border-red-200 bg-red-50 text-red-900"
          : "border-emerald-200 bg-emerald-50 text-emerald-900",
      )}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

function UnobservedState({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-xl border border-dashed border-black/[0.12] px-4 py-5 text-center text-xs text-[#777771]">
      {children}
    </div>
  );
}

function SkillsEmptyState() {
  return (
    <div className="mt-8 flex min-h-[38vh] flex-col items-center justify-center rounded-2xl border border-dashed border-black/[0.12] px-6 text-center">
      <GitCompareArrowsIcon
        className="size-6 text-[#777771]"
        aria-hidden="true"
      />
      <h2 className="mt-4 text-base font-semibold text-[#353530]">
        还没有技能候选
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#777771]">
        只有绑定冻结实验、通过安全扫描并保留失败来源的候选，才会进入这里。
      </p>
    </div>
  );
}

function FilteredEmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-black/[0.12] px-5 py-10 text-center text-sm text-[#777771]">
      当前筛选下没有候选版本。
    </div>
  );
}

function skillsErrorMessage(error: unknown) {
  if (error instanceof CommerceApiError) {
    if (error.code === "workspace_missing") {
      return "当前工作区不可用，无法读取技能候选。";
    }
    if (error.code === "invalid_response") {
      return "技能候选或实验依据未通过前端合同校验。";
    }
    if (error.status === 409) {
      return "技能状态已经变化，或当前版本不满足人工晋级/回滚门禁。";
    }
    if (error.status === 503) {
      return "技能治理服务暂时不可用，本次操作没有执行。";
    }
  }
  return "技能治理请求失败，本次操作没有被视为成功。";
}
