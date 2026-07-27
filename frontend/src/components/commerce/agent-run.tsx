"use client";

import {
  ArrowLeftIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleAlertIcon,
  CircleDashedIcon,
  Clock3Icon,
  GitBranchIcon,
  ListTreeIcon,
  LoaderCircleIcon,
  SearchIcon,
  ShieldCheckIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildCommerceAgentRunViewModel,
  CommerceApiError,
  filterCommerceRunItems,
  loadCommerceAgentRunSnapshot,
  type CommerceAgentRunSnapshot,
  type CommerceAgentRunViewModel,
  type CommerceCase,
  type CommerceRunFilter,
  type CommerceRunStageStatus,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

export function CommerceAgentRun({
  workspaceId,
  cases,
  preferredRunId = null,
  refreshSignal = 0,
  onOpenCase,
}: {
  workspaceId: string | null;
  cases: CommerceCase[];
  preferredRunId?: string | null;
  refreshSignal?: number;
  onOpenCase: (caseId: string) => void;
}) {
  const [snapshot, setSnapshot] = useState<CommerceAgentRunSnapshot | null>(
    null,
  );
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [filter, setFilter] = useState<CommerceRunFilter>("all");
  const [query, setQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAuditTrail, setShowAuditTrail] = useState(false);
  const caseIdsKey = cases.map((item) => item.id).join("|");

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    void loadCommerceAgentRunSnapshot({
      workspaceId: workspaceId ?? "",
      caseIds: cases.map((item) => item.id),
      selectedRunId: selectedRunId ?? preferredRunId ?? undefined,
      signal: controller.signal,
    })
      .then((result) => {
        setSnapshot(result);
        setSelectedRunId(
          result.selectedDetail?.run.id ?? result.runs[0]?.id ?? null,
        );
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") {
          return;
        }
        setError(runErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [
    caseIdsKey,
    cases,
    preferredRunId,
    refreshSignal,
    reloadKey,
    selectedRunId,
    workspaceId,
  ]);

  const viewModel = useMemo(
    () =>
      buildCommerceAgentRunViewModel({
        cases,
        runs: snapshot?.runs ?? [],
        selectedRunId,
        selectedDetail: snapshot?.selectedDetail ?? null,
        events: snapshot?.events ?? [],
        checkpoints: snapshot?.checkpoints ?? [],
      }),
    [cases, selectedRunId, snapshot],
  );

  return (
    <CommerceAgentRunView
      viewModel={viewModel}
      filter={filter}
      query={query}
      isLoading={isLoading}
      error={error}
      showAuditTrail={showAuditTrail}
      onFilterChange={setFilter}
      onQueryChange={setQuery}
      onSelectRun={(runId) => {
        setSelectedRunId(runId);
        setShowAuditTrail(false);
      }}
      onOpenCase={onOpenCase}
      onShowEvents={() => setShowAuditTrail((value) => !value)}
      onRetry={() => setReloadKey((value) => value + 1)}
    />
  );
}

export function CommerceAgentRunView({
  viewModel,
  filter,
  query,
  isLoading,
  error,
  showAuditTrail = false,
  onFilterChange,
  onQueryChange,
  onSelectRun,
  onOpenCase,
  onShowEvents,
  onRetry,
}: {
  viewModel: CommerceAgentRunViewModel;
  filter: CommerceRunFilter;
  query: string;
  isLoading: boolean;
  error: string | null;
  showAuditTrail?: boolean;
  onFilterChange: (value: CommerceRunFilter) => void;
  onQueryChange: (value: string) => void;
  onSelectRun: (runId: string) => void;
  onOpenCase: (caseId: string) => void;
  onShowEvents: () => void;
  onRetry?: () => void;
}) {
  const items = useMemo(
    () => filterCommerceRunItems(viewModel.items, { filter, query }),
    [filter, query, viewModel.items],
  );
  const selected = viewModel.selected;

  return (
    <section
      className="mx-auto w-full max-w-[1240px] px-5 py-7 sm:px-8 lg:px-9"
      data-testid="commerce-agent-run"
    >
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.03em] text-[#292925]">
          {viewModel.title}
        </h1>
        <p className="mt-2 max-w-[780px] text-sm leading-6 text-[#6f6f69]">
          {viewModel.subtitle}
        </p>
      </div>

      <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div
          className="flex gap-2 overflow-x-auto pb-1 xl:pb-0"
          aria-label="运行状态筛选"
        >
          {viewModel.filters.map((item) => (
            <button
              type="button"
              key={item.value}
              aria-pressed={filter === item.value}
              className={cn(
                "min-h-10 shrink-0 rounded-lg border px-3 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2",
                item.count === 0 && "hidden sm:block",
                filter === item.value
                  ? "border-[#252522] bg-[#252522] text-white"
                  : "border-black/[0.08] bg-[#fafaf8] text-[#61615b] hover:bg-black/[0.04]",
              )}
              onClick={() => onFilterChange(item.value)}
            >
              {item.label}
              <span className="ml-1.5 opacity-70">{item.count}</span>
            </button>
          ))}
        </div>
        <label className="flex min-h-10 w-full items-center gap-2 rounded-lg border border-black/[0.09] bg-white px-3 text-sm xl:w-[280px]">
          <SearchIcon
            className="size-4 shrink-0 text-[#777771]"
            aria-hidden="true"
          />
          <span className="sr-only">搜索运行或案例</span>
          <input
            type="search"
            value={query}
            placeholder="搜索运行或案例"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#9a9a94]"
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>
      </div>

      {error && (
        <div
          className="mt-4 flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
          role="alert"
        >
          <div className="flex items-start gap-3">
            <CircleAlertIcon
              className="mt-0.5 size-4 shrink-0"
              aria-hidden="true"
            />
            <p>{error}</p>
          </div>
          {onRetry && (
            <button
              type="button"
              className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2"
              onClick={onRetry}
            >
              重试
            </button>
          )}
        </div>
      )}

      {isLoading && viewModel.items.length === 0 ? (
        <div className="mt-8 flex min-h-[38vh] items-center justify-center text-sm text-[#74746e]">
          <LoaderCircleIcon
            className="mr-2 size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          正在读取运行记录
        </div>
      ) : viewModel.items.length === 0 ? (
        <RunEmptyState />
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <RunQueue
            items={items}
            selected={selected}
            onSelectRun={onSelectRun}
          />

          {selected ? (
            <div className="min-w-0 overflow-hidden rounded-2xl border border-black/[0.09] bg-white shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              <RunDocumentHeader selected={selected} />
              <div className="min-[1480px]:grid min-[1480px]:grid-cols-[minmax(0,1fr)_390px]">
                <RunGraph selected={selected} />
                <RunEngineeringDetail selected={selected} />
              </div>
              <RunDocumentActions
                selected={selected}
                showAuditTrail={showAuditTrail}
                onOpenCase={onOpenCase}
                onShowEvents={onShowEvents}
              />
              {showAuditTrail && <RunAuditTrail selected={selected} />}
            </div>
          ) : (
            <FilteredEmptyState />
          )}
        </div>
      )}
    </section>
  );
}

function RunQueue({
  items,
  selected,
  onSelectRun,
}: {
  items: CommerceAgentRunViewModel["items"];
  selected: CommerceAgentRunViewModel["selected"];
  onSelectRun: (runId: string) => void;
}) {
  return (
    <div>
      {selected && (
        <div className="relative rounded-xl border border-black/[0.09] bg-white p-4 xl:hidden">
          <select
            aria-label="切换运行"
            value={selected.id}
            className="absolute inset-0 z-10 size-full cursor-pointer appearance-none opacity-0"
            onChange={(event) => onSelectRun(event.target.value)}
          >
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} · {item.statusLabel}
              </option>
            ))}
          </select>
          <div className="flex items-start gap-3">
            <RunStatusIcon status={selected.statusGroup} />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-[#343430]">
                    {selected.title}
                  </h2>
                  <p className="mt-1 text-xs text-[#777771]">
                    {selected.caseTitle} · {selected.typeLabel}
                  </p>
                </div>
                <ChevronDownIcon
                  className="mt-0.5 size-4 shrink-0 text-[#777771]"
                  aria-hidden="true"
                />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusChip status={selected.statusGroup}>
                  {selected.statusLabel}
                </StatusChip>
                <span className="text-[11px] text-[#777771]">
                  {selected.shortId} · {selected.durationLabel}
                </span>
              </div>
              <p className="mt-2 text-xs text-[#666660]">
                {selected.pathCountLabel} · {selected.stopReasonLabel}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="hidden space-y-2 xl:block" aria-label="运行队列">
        {items.map((item) => (
          <button
            type="button"
            key={item.id}
            aria-current={item.id === selected?.id ? "true" : undefined}
            className={cn(
              "w-full rounded-xl border px-4 py-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2",
              item.id === selected?.id
                ? "border-[#343431] bg-[#fcfcfa]"
                : "border-black/[0.08] bg-white hover:bg-[#fafaf8]",
            )}
            onClick={() => onSelectRun(item.id)}
          >
            <div className="flex items-start gap-3">
              <RunStatusIcon status={item.statusGroup} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-[#363632]">
                  {item.title}
                </p>
                <p className="mt-1 truncate text-xs text-[#777771]">
                  {item.caseTitle} · {item.typeLabel}
                </p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <StatusChip status={item.statusGroup}>
                    {item.statusLabel}
                  </StatusChip>
                  <span className="text-[11px] text-[#85857e]">
                    {item.timeLabel}
                  </span>
                </div>
                <p className="mt-2 truncate text-[11px] text-[#777771]">
                  {item.pathCountLabel} · {item.stopReasonLabel}
                </p>
              </div>
            </div>
          </button>
        ))}
        {items.length === 0 && <FilteredEmptyState />}
      </div>
    </div>
  );
}

function RunDocumentHeader({
  selected,
}: {
  selected: NonNullable<CommerceAgentRunViewModel["selected"]>;
}) {
  return (
    <header className="border-b border-black/[0.07] px-5 py-5 sm:px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold tracking-[-0.02em] text-[#2e2e2a]">
              {selected.title}
            </h2>
            <StatusChip status={selected.statusGroup}>
              {selected.statusLabel}
            </StatusChip>
            <StatusChip>{selected.typeLabel}</StatusChip>
          </div>
          <p className="mt-2 text-xs text-[#777771]">
            {selected.shortId} · {selected.periodLabel} ·{" "}
            {selected.durationLabel}
          </p>
          <p className="mt-2 text-sm leading-6 text-[#5f5f59]">
            停止原因：{selected.stopReasonLabel}
          </p>
        </div>
      </div>
    </header>
  );
}

function RunGraph({
  selected,
}: {
  selected: NonNullable<CommerceAgentRunViewModel["selected"]>;
}) {
  return (
    <section className="min-w-0 px-5 py-5 sm:px-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-[#33332f]">运行图</h3>
        <span className="text-[11px] text-[#85857e]">
          {selected.stages.length} 个阶段
        </span>
      </div>
      <ol className="overflow-hidden rounded-xl border border-black/[0.08] bg-white">
        {selected.stages.map((stage, index) => (
          <li
            key={stage.key}
            className="relative border-b border-black/[0.07] px-4 py-4 last:border-b-0"
          >
            <div className="flex items-start gap-3">
              <StageMarker index={index} status={stage.status} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold text-[#353531]">
                    {stage.title}
                  </h4>
                  <StatusChip status={stage.status}>
                    {stage.statusLabel}
                  </StatusChip>
                </div>
                <p className="mt-1 text-xs leading-5 text-[#6f6f69]">
                  {stage.description}
                </p>
                {stage.kind === "fanout" && (
                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    {stage.paths.map((path) => (
                      <div
                        key={path.pathType}
                        className={cn(
                          "rounded-lg border px-3 py-3",
                          path.status === "completed"
                            ? "border-emerald-200 bg-emerald-50/35"
                            : path.status === "blocked"
                              ? "border-red-200 bg-red-50/40"
                              : "border-black/[0.08] bg-[#fafaf8]",
                        )}
                      >
                        <p className="text-xs font-semibold text-[#3e3e39]">
                          {path.label}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <StatusChip status={path.status}>
                            {path.statusLabel}
                          </StatusChip>
                          <span className="text-[11px] text-[#73736d]">
                            {path.evidenceCountLabel}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {stage.derivationLabel && (
                  <p className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-[#f5f5f2] px-2 py-1 text-[11px] leading-5 text-[#666660]">
                    <GitBranchIcon className="size-3" aria-hidden="true" />
                    {stage.derivationLabel}
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function RunEngineeringDetail({
  selected,
}: {
  selected: NonNullable<CommerceAgentRunViewModel["selected"]>;
}) {
  return (
    <aside className="border-t border-black/[0.07] bg-[#fcfcfa] min-[1480px]:border-t-0 min-[1480px]:border-l">
      <DocumentSection title="运行详情" border={false}>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/35 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-[#33332f]">
              {selected.selectedStageTitle}
            </p>
            <StatusChip status="completed">已完成</StatusChip>
          </div>
          <p className="mt-1 text-xs leading-5 text-[#666660]">
            {selected.selectedStageDescription}
          </p>
        </div>
      </DocumentSection>

      <DocumentSection title="模型调用">
        <DefinitionList
          rows={[
            ["实际模型", selected.telemetry.modelIdentityLabel],
            ["请求编号", selected.telemetry.requestCountLabel],
            ["令牌用量", selected.telemetry.tokenLabel],
            ["总延迟", selected.telemetry.latencyLabel],
            ["重试", selected.telemetry.retryLabel],
            ["停止原因", selected.telemetry.stopReasonLabel],
          ]}
        />
      </DocumentSection>

      <DocumentSection title="预算">
        {selected.budget.length > 0 ? (
          <div className="space-y-3">
            {selected.budget.map((row) => (
              <div
                key={row.label}
                className="grid grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-3 text-xs"
              >
                <span className="font-medium text-[#555550]">{row.label}</span>
                <div className="h-1.5 overflow-hidden rounded-full bg-black/[0.06]">
                  <div
                    className="h-full rounded-full bg-emerald-700"
                    style={{ width: `${Math.round(row.ratio * 100)}%` }}
                  />
                </div>
                <span className="text-right text-[#666660] tabular-nums">
                  {row.valueLabel}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <UnobservedState>预算快照未观察</UnobservedState>
        )}
      </DocumentSection>

      <DocumentSection title="最新检查点">
        {selected.checkpoint ? (
          <dl className="grid grid-cols-2 overflow-hidden rounded-xl border border-black/[0.08] bg-white text-center text-xs min-[1480px]:grid-cols-5 sm:grid-cols-5">
            {[
              ["序号", selected.checkpoint.sequenceLabel],
              ["循环", selected.checkpoint.iterationLabel],
              ["证据", selected.checkpoint.evidenceLabel],
              ["工作假设", selected.checkpoint.hypothesisLabel],
              ["上下文 SHA-256", selected.checkpoint.contextLabel],
            ].map(([label, value]) => (
              <div
                key={label}
                className="border-r border-b border-black/[0.06] px-2 py-3 last:border-r-0 sm:border-b-0"
              >
                <dt className="text-[10px] text-[#777771]">{label}</dt>
                <dd className="mt-1 font-medium text-[#454540]">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <UnobservedState>检查点未观察</UnobservedState>
        )}
      </DocumentSection>

      <DocumentSection title="审计边界">
        <p className="text-xs leading-5 text-[#666660]">
          {selected.auditBoundary}
        </p>
        {selected.wasReordered && (
          <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-900">
            接收顺序与 run_sequence 不一致，页面已按权威序号重排。
          </p>
        )}
      </DocumentSection>
    </aside>
  );
}

function RunDocumentActions({
  selected,
  showAuditTrail,
  onOpenCase,
  onShowEvents,
}: {
  selected: NonNullable<CommerceAgentRunViewModel["selected"]>;
  showAuditTrail: boolean;
  onOpenCase: (caseId: string) => void;
  onShowEvents: () => void;
}) {
  return (
    <div className="flex flex-col-reverse gap-2 border-t border-black/[0.07] px-5 py-4 sm:flex-row sm:px-6">
      <button
        type="button"
        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-black/[0.1] bg-white px-4 text-xs font-medium text-[#4e4e49] hover:bg-black/[0.03] focus-visible:outline-2 focus-visible:outline-offset-2"
        onClick={() => onOpenCase(selected.caseId)}
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" />
        返回案例
      </button>
      <button
        type="button"
        aria-expanded={showAuditTrail}
        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-[#30302d] bg-[#30302d] px-4 text-xs font-medium text-white hover:bg-[#1f1f1d] focus-visible:outline-2 focus-visible:outline-offset-2"
        onClick={onShowEvents}
      >
        <ListTreeIcon className="size-4" aria-hidden="true" />
        {showAuditTrail ? "收起事件流" : "查看事件流"}
      </button>
    </div>
  );
}

function RunAuditTrail({
  selected,
}: {
  selected: NonNullable<CommerceAgentRunViewModel["selected"]>;
}) {
  return (
    <section className="border-t border-black/[0.07] bg-[#fafaf8] px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-[#33332f]">事件与检查点</h3>
        <p className="text-[11px] text-[#777771]">
          {selected.eventCountLabel} · {selected.checkpointCountLabel}
        </p>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="overflow-hidden rounded-xl border border-black/[0.08] bg-white">
          <div className="border-b border-black/[0.07] px-4 py-3 text-xs font-semibold text-[#454540]">
            领域事件
          </div>
          {selected.events.length > 0 ? (
            <ol>
              {selected.events.map((event) => (
                <li
                  key={event.id}
                  className="grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 border-b border-black/[0.06] px-4 py-3 text-xs last:border-b-0"
                >
                  <span className="font-mono text-[10px] text-[#85857e]">
                    {event.sequenceLabel}
                  </span>
                  <span className="text-[#555550]">{event.title}</span>
                  <span className="text-[10px] text-[#85857e]">
                    {event.timeLabel}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <UnobservedState>事件未观察</UnobservedState>
          )}
        </div>
        <div className="overflow-hidden rounded-xl border border-black/[0.08] bg-white">
          <div className="border-b border-black/[0.07] px-4 py-3 text-xs font-semibold text-[#454540]">
            检查点
          </div>
          {selected.checkpoints.length > 0 ? (
            <ol>
              {selected.checkpoints.map((checkpoint) => (
                <li
                  key={checkpoint.id}
                  className="grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 border-b border-black/[0.06] px-4 py-3 text-xs last:border-b-0"
                >
                  <span className="font-mono text-[10px] text-[#85857e]">
                    {checkpoint.sequenceLabel}
                  </span>
                  <span className="text-[#555550]">
                    循环 {checkpoint.iterationLabel} · 证据{" "}
                    {checkpoint.evidenceLabel} · 工作假设{" "}
                    {checkpoint.hypothesisLabel}
                  </span>
                  <span className="text-[10px] text-[#85857e]">
                    {checkpoint.createdLabel}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <UnobservedState>检查点未观察</UnobservedState>
          )}
        </div>
      </div>
    </section>
  );
}

function StageMarker({
  index,
  status,
}: {
  index: number;
  status: CommerceRunStageStatus;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <span
        className={cn(
          "flex size-6 items-center justify-center rounded-full text-[11px] font-semibold",
          status === "completed"
            ? "bg-emerald-700 text-white"
            : status === "blocked"
              ? "bg-red-600 text-white"
              : status === "running"
                ? "bg-blue-600 text-white"
                : "border border-black/[0.1] bg-[#fafaf8] text-[#777771]",
        )}
      >
        {status === "completed" ? (
          <CheckCircle2Icon className="size-3.5" aria-hidden="true" />
        ) : status === "blocked" ? (
          <XCircleIcon className="size-3.5" aria-hidden="true" />
        ) : (
          index + 1
        )}
      </span>
    </div>
  );
}

function RunStatusIcon({ status }: { status: string }) {
  if (status === "completed") {
    return (
      <CheckCircle2Icon
        className="mt-0.5 size-5 shrink-0 text-emerald-700"
        aria-hidden="true"
      />
    );
  }
  if (status === "failed") {
    return (
      <XCircleIcon
        className="mt-0.5 size-5 shrink-0 text-red-600"
        aria-hidden="true"
      />
    );
  }
  if (status === "waiting") {
    return (
      <Clock3Icon
        className="mt-0.5 size-5 shrink-0 text-amber-600"
        aria-hidden="true"
      />
    );
  }
  return (
    <CircleDashedIcon
      className="mt-0.5 size-5 shrink-0 text-blue-600"
      aria-hidden="true"
    />
  );
}

function StatusChip({
  status = "neutral",
  children,
}: {
  status?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-md border px-2 py-1 text-[10px] font-medium whitespace-nowrap",
        status === "completed" &&
          "border-emerald-200 bg-emerald-50 text-emerald-700",
        status === "failed" || status === "blocked"
          ? "border-red-200 bg-red-50 text-red-700"
          : null,
        status === "running" && "border-blue-200 bg-blue-50 text-blue-700",
        status === "waiting" && "border-amber-200 bg-amber-50 text-amber-700",
        (status === "neutral" || status === "not_started") &&
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
}: {
  title: string;
  children: React.ReactNode;
  border?: boolean;
}) {
  return (
    <section
      className={cn(
        "px-5 py-5 sm:px-6",
        border && "border-t border-black/[0.07]",
      )}
    >
      <h3 className="mb-3 text-sm font-semibold text-[#33332f]">{title}</h3>
      {children}
    </section>
  );
}

function DefinitionList({ rows }: { rows: Array<[string, string]> }) {
  return (
    <dl className="overflow-hidden rounded-xl border border-black/[0.08] bg-white text-xs">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="grid grid-cols-[88px_minmax(0,1fr)] gap-3 border-b border-black/[0.06] px-3 py-2.5 last:border-b-0"
        >
          <dt className="font-medium text-[#555550]">{label}</dt>
          <dd className="min-w-0 text-right break-all text-[#5f5f59] tabular-nums">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function UnobservedState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-black/[0.12] px-4 py-5 text-center text-xs text-[#777771]">
      {children}
    </div>
  );
}

function RunEmptyState() {
  return (
    <div className="mt-8 flex min-h-[38vh] flex-col items-center justify-center rounded-2xl border border-dashed border-black/[0.12] px-6 text-center">
      <ShieldCheckIcon className="size-6 text-[#777771]" aria-hidden="true" />
      <h2 className="mt-4 text-base font-semibold text-[#353530]">
        还没有运行记录
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#777771]">
        数据接入、案例调查、行动执行或后续跟踪真正启动后，持久化运行会显示在这里。
      </p>
    </div>
  );
}

function FilteredEmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-black/[0.12] px-5 py-10 text-center text-sm text-[#777771]">
      当前筛选下没有运行记录。
    </div>
  );
}

function runErrorMessage(error: unknown): string {
  if (error instanceof CommerceApiError) {
    if (error.code === "workspace_missing") {
      return "当前工作区不可用，无法读取运行记录。";
    }
    if (error.code === "invalid_response") {
      return "运行数据未通过前端合同校验。";
    }
    if (error.status === 503) {
      return "运行记录服务暂时不可用，没有把本次读取视为成功。";
    }
  }
  return "运行记录读取失败，没有把缺失数据推断为完成。";
}
