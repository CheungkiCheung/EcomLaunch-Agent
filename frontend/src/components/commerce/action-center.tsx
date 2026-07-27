"use client";

import {
  ArrowLeftIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  FileSearchIcon,
  LoaderCircleIcon,
  PlayIcon,
  RotateCcwIcon,
  SearchIcon,
  ShieldCheckIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildCommerceActionCenterViewModel,
  CommerceApiError,
  decideCommerceActionApproval,
  executeCommerceAction,
  filterCommerceActionItems,
  loadCommerceActionCenterSnapshot,
  type CommerceActionCenterSnapshot,
  type CommerceActionCenterViewModel,
  type CommerceActionFilter,
  type CommerceCase,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

export function CommerceActionCenter({
  workspaceId,
  actorId,
  cases,
  preferredActionId = null,
  refreshSignal = 0,
  onOpenCase,
  onOpenEvidence,
}: {
  workspaceId: string | null;
  actorId: string | null;
  cases: CommerceCase[];
  preferredActionId?: string | null;
  refreshSignal?: number;
  onOpenCase: (caseId: string) => void;
  onOpenEvidence: (caseId: string) => void;
}) {
  const [snapshot, setSnapshot] = useState<CommerceActionCenterSnapshot | null>(
    null,
  );
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [filter, setFilter] = useState<CommerceActionFilter>("all");
  const [query, setQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const caseIdsKey = cases.map((item) => item.id).join("|");

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    loadCommerceActionCenterSnapshot({
      workspaceId: workspaceId ?? "",
      caseIds: cases.map((item) => item.id),
      selectedActionId: selectedActionId ?? preferredActionId ?? undefined,
      signal: controller.signal,
    })
      .then((result) => {
        setSnapshot(result);
        setSelectedActionId(
          result.selectedDetail?.record.action.id ??
            result.records[0]?.action.id ??
            null,
        );
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError")
          return;
        setError(actionErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [
    caseIdsKey,
    cases,
    preferredActionId,
    refreshSignal,
    reloadKey,
    selectedActionId,
    workspaceId,
  ]);

  const viewModel = useMemo(
    () =>
      buildCommerceActionCenterViewModel({
        cases,
        records: snapshot?.records ?? [],
        selectedActionId,
        selectedDetail: snapshot?.selectedDetail ?? null,
      }),
    [cases, selectedActionId, snapshot],
  );

  const submitPrimaryAction = async () => {
    const selected = viewModel.selected;
    if (!selected || !workspaceId || !actorId || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      if (selected.canApprove) {
        const result = await decideCommerceActionApproval({
          workspaceId,
          actorId,
          actionId: selected.id,
          decision: "approve",
          idempotencyKey: `approve-${selected.id}`,
        });
        setNotice(
          result.approval.status === "approved"
            ? "审批已完成，行动现在可以执行。"
            : `已记录你的批准，还需要 ${result.approval.required_approvals - result.approval.approved_actor_ids.length} 人批准。`,
        );
      } else {
        const operation = selected.canRollback ? "rollback" : "execute";
        const result = await executeCommerceAction({
          workspaceId,
          actorId,
          actionId: selected.id,
          operation,
          idempotencyKey: `${operation}-${selected.id}`,
        });
        setNotice(
          operation === "rollback"
            ? result.replayed
              ? "已读取同一回滚请求的既有结果。"
              : "回滚已完成，执行产物已重新验证。"
            : result.replayed
              ? "已读取同一执行请求的既有结果。"
              : "行动已执行，并已创建可审计运行与执行产物。",
        );
      }
      setReloadKey((value) => value + 1);
    } catch (cause) {
      setError(actionErrorMessage(cause));
    } finally {
      setIsSubmitting(false);
    }
  };

  const rejectAction = async (reason: string) => {
    const selected = viewModel.selected;
    if (!selected || !workspaceId || !actorId || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await decideCommerceActionApproval({
        workspaceId,
        actorId,
        actionId: selected.id,
        decision: "reject",
        idempotencyKey: `reject-${selected.id}`,
        reason,
      });
      setNotice("审批已拒绝，原行动不会继续执行。历史记录保持不可变。 ");
      setReloadKey((value) => value + 1);
    } catch (cause) {
      setError(actionErrorMessage(cause));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <CommerceActionCenterView
      viewModel={viewModel}
      filter={filter}
      query={query}
      isLoading={isLoading}
      isSubmitting={isSubmitting}
      notice={notice}
      error={error}
      actorAvailable={Boolean(actorId?.trim())}
      onFilterChange={setFilter}
      onQueryChange={setQuery}
      onSelectAction={(actionId) => {
        setSelectedActionId(actionId);
        setNotice(null);
        setError(null);
      }}
      onOpenCase={onOpenCase}
      onOpenEvidence={onOpenEvidence}
      onPrimaryAction={submitPrimaryAction}
      onReject={rejectAction}
    />
  );
}

export function CommerceActionCenterView({
  viewModel,
  filter,
  query,
  isLoading,
  isSubmitting,
  notice,
  error,
  actorAvailable,
  onFilterChange,
  onQueryChange,
  onSelectAction,
  onOpenCase,
  onOpenEvidence,
  onPrimaryAction,
  onReject,
}: {
  viewModel: CommerceActionCenterViewModel;
  filter: CommerceActionFilter;
  query: string;
  isLoading: boolean;
  isSubmitting: boolean;
  notice: string | null;
  error: string | null;
  actorAvailable: boolean;
  onFilterChange: (value: CommerceActionFilter) => void;
  onQueryChange: (value: string) => void;
  onSelectAction: (actionId: string) => void;
  onOpenCase: (caseId: string) => void;
  onOpenEvidence: (caseId: string) => void;
  onPrimaryAction: () => void;
  onReject: (reason: string) => void;
}) {
  const [rejectReason, setRejectReason] = useState("");
  const items = useMemo(
    () => filterCommerceActionItems(viewModel.items, { filter, query }),
    [filter, query, viewModel.items],
  );
  const selected = viewModel.selected;

  return (
    <section className="mx-auto w-full max-w-[1180px] px-5 py-7 sm:px-8 lg:px-9">
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.03em] text-[#292925]">
          {viewModel.title}
        </h1>
        <p className="mt-2 max-w-[760px] text-sm leading-6 text-[#6f6f69]">
          {viewModel.subtitle}
        </p>
      </div>

      <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div
          className="flex gap-2 overflow-x-auto pb-1 xl:pb-0"
          aria-label="行动状态筛选"
        >
          {viewModel.filters.map((item) => (
            <button
              type="button"
              key={item.value}
              aria-pressed={filter === item.value}
              className={cn(
                "min-h-10 shrink-0 rounded-lg border px-3 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2",
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
          <span className="sr-only">搜索行动或案例</span>
          <input
            type="search"
            value={query}
            placeholder="搜索行动或案例"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#9a9a94]"
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>
      </div>

      {error && (
        <div
          className="mt-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
          role="alert"
        >
          <CircleAlertIcon
            className="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />
          <p>{error}</p>
        </div>
      )}
      {notice && (
        <div
          className="mt-4 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
          role="status"
        >
          <CheckCircle2Icon
            className="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />
          <p>{notice}</p>
        </div>
      )}

      {isLoading && viewModel.items.length === 0 ? (
        <div className="mt-8 flex min-h-[38vh] items-center justify-center text-sm text-[#74746e]">
          <LoaderCircleIcon
            className="mr-2 size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          正在读取行动记录
        </div>
      ) : viewModel.items.length === 0 ? (
        <ActionEmptyState />
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
          <div>
            <label className="block xl:hidden">
              <span className="sr-only">切换行动</span>
              <div className="relative">
                <select
                  value={selected?.id ?? ""}
                  className="min-h-12 w-full appearance-none rounded-xl border border-black/[0.09] bg-white px-4 pr-10 text-sm font-medium outline-none"
                  onChange={(event) => onSelectAction(event.target.value)}
                >
                  {items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title} · {item.statusLabel}
                    </option>
                  ))}
                </select>
                <ChevronDownIcon
                  className="pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-[#777771]"
                  aria-hidden="true"
                />
              </div>
            </label>

            <div className="hidden space-y-2 xl:block" aria-label="行动队列">
              {items.map((item) => (
                <ActionQueueCard
                  key={item.id}
                  item={item}
                  active={item.id === selected?.id}
                  onSelect={() => onSelectAction(item.id)}
                />
              ))}
              {items.length === 0 && <FilteredEmptyState />}
            </div>

            {selected && (
              <div className="mt-3 rounded-xl border border-black/[0.09] bg-white p-4 xl:hidden">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-[#343430]">
                      {selected.title}
                    </h2>
                    <p className="mt-1 text-xs text-[#777771]">
                      {selected.caseTitle}
                    </p>
                  </div>
                  <StatusChip tone="status">{selected.statusLabel}</StatusChip>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <StatusChip tone="risk">{selected.riskLabel}</StatusChip>
                  <StatusChip>{selected.policyLabel}</StatusChip>
                  <span className="ml-auto text-[11px] text-[#85857e]">
                    {selected.approvalLabel} · {selected.updatedLabel}
                  </span>
                </div>
              </div>
            )}
          </div>

          {selected ? (
            <ActionDetailDocument
              selected={selected}
              actorAvailable={actorAvailable}
              isSubmitting={isSubmitting}
              rejectReason={rejectReason}
              onRejectReasonChange={setRejectReason}
              onOpenCase={() => onOpenCase(selected.caseId)}
              onOpenEvidence={() => onOpenEvidence(selected.caseId)}
              onPrimaryAction={onPrimaryAction}
              onReject={() => onReject(rejectReason)}
            />
          ) : (
            <FilteredEmptyState />
          )}
        </div>
      )}
    </section>
  );
}

function ActionQueueCard({
  item,
  active,
  onSelect,
}: {
  item: CommerceActionCenterViewModel["items"][number];
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "w-full rounded-xl border bg-white px-4 py-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2",
        active
          ? "border-[#353530] shadow-[0_2px_8px_rgba(0,0,0,0.05)]"
          : "border-black/[0.08] hover:bg-[#fcfcfa]",
      )}
      onClick={onSelect}
    >
      <h2 className="text-sm leading-5 font-semibold text-[#353530]">
        {item.title}
      </h2>
      <p className="mt-1 text-xs text-[#777771]">{item.caseTitle}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <StatusChip tone="status">{item.statusLabel}</StatusChip>
        <StatusChip tone="risk">{item.riskLabel}</StatusChip>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-[#85857e]">
        <span>
          {item.approvalLabel} · {item.policyLabel}
        </span>
        <span>{item.updatedLabel}</span>
      </div>
    </button>
  );
}

function ActionDetailDocument({
  selected,
  actorAvailable,
  isSubmitting,
  rejectReason,
  onRejectReasonChange,
  onOpenCase,
  onOpenEvidence,
  onPrimaryAction,
  onReject,
}: {
  selected: NonNullable<CommerceActionCenterViewModel["selected"]>;
  actorAvailable: boolean;
  isSubmitting: boolean;
  rejectReason: string;
  onRejectReasonChange: (value: string) => void;
  onOpenCase: () => void;
  onOpenEvidence: () => void;
  onPrimaryAction: () => void;
  onReject: () => void;
}) {
  return (
    <article className="overflow-hidden rounded-xl border border-black/[0.08] bg-white">
      <div className="px-5 py-5 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-medium text-[#777771]">行动详情</p>
            <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.025em] text-[#292925]">
              {selected.title}
            </h2>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <StatusChip tone="status">{selected.statusLabel}</StatusChip>
            <StatusChip tone="risk">{selected.riskLabel}</StatusChip>
            <StatusChip>{selected.policyLabel}</StatusChip>
          </div>
        </div>
        <p className="mt-3 max-w-[760px] text-sm leading-6 text-[#62625c]">
          {selected.description}
        </p>
      </div>

      <DocumentSection title="为什么建议这样做">
        <div className="flex flex-col gap-3 rounded-xl border border-black/[0.08] bg-[#fcfcfa] px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#eef6ef] text-[#477b50]">
              <FileSearchIcon className="size-4" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-medium text-[#393934]">
                {selected.hypothesisSummary}
              </p>
              <p className="mt-1 text-xs leading-5 text-[#777771]">
                {selected.evidenceSummary}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 self-start rounded-lg px-2 text-sm font-medium text-[#315f9b] hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 sm:self-auto"
            onClick={onOpenEvidence}
          >
            查看证据
            <ChevronRightIcon className="size-4" aria-hidden="true" />
          </button>
        </div>
      </DocumentSection>

      <div className="grid gap-0 border-t border-black/[0.07] lg:grid-cols-2">
        <DocumentSection title="执行计划" border={false}>
          <DefinitionList rows={selected.planRows} />
        </DocumentSection>
        <DocumentSection title="策略与权限" border={false} sideBorder>
          <div
            className={cn(
              "rounded-xl border px-4 py-4",
              selected.policyDispositionLabel === "允许执行"
                ? "border-emerald-200 bg-emerald-50/60"
                : selected.policyDispositionLabel === "策略已阻止"
                  ? "border-red-200 bg-red-50/60"
                  : "border-amber-200 bg-amber-50/60",
            )}
          >
            <div className="flex items-start gap-3">
              <ShieldCheckIcon
                className="mt-0.5 size-5 shrink-0 text-[#3f8250]"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-semibold text-[#356b41]">
                  {selected.policyDispositionLabel}
                </p>
                <p className="mt-1 text-xs leading-5 text-[#5f6f60]">
                  {selected.policyDescription}
                </p>
              </div>
            </div>
            <dl className="mt-4 divide-y divide-black/[0.06] border-t border-black/[0.07] text-xs">
              <DefinitionRow
                label="策略等级"
                value={selected.policyLabel.replace("策略 ", "")}
              />
              <DefinitionRow
                label="执行工具"
                value={selected.executionToolLabel}
                mono
              />
              {selected.approvalProgressLabel && (
                <DefinitionRow
                  label="审批进度"
                  value={selected.approvalProgressLabel}
                />
              )}
              {selected.artifactLabel && (
                <DefinitionRow
                  label="执行产物"
                  value={selected.artifactLabel}
                />
              )}
            </dl>
          </div>
        </DocumentSection>
      </div>

      <DocumentSection title="回滚方案">
        <DefinitionList
          rows={[
            { label: "回滚操作", value: selected.rollback.strategy },
            { label: "触发条件", value: selected.rollback.trigger },
            { label: "验证方式", value: selected.rollback.verification },
          ]}
        />
      </DocumentSection>

      {selected.canReject && (
        <div className="border-t border-black/[0.07] bg-[#fcfcfa] px-5 py-5 sm:px-6">
          <label className="block">
            <span className="text-xs font-medium text-[#4f4f49]">
              审批意见（拒绝时建议填写）
            </span>
            <textarea
              rows={2}
              value={rejectReason}
              className="mt-2 w-full resize-y rounded-lg border border-black/[0.09] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
              placeholder="说明需要补充的证据或策略原因"
              onChange={(event) => onRejectReasonChange(event.target.value)}
            />
          </label>
        </div>
      )}

      <div className="border-t border-black/[0.07] bg-[#fcfcfa] px-5 py-4 sm:px-6">
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-black/[0.09] bg-white px-4 text-sm font-medium hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={onOpenCase}
          >
            <ArrowLeftIcon className="size-4" aria-hidden="true" />
            返回案例
          </button>
          {selected.canReject && (
            <button
              type="button"
              disabled={isSubmitting || !actorAvailable}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-red-200 bg-white px-4 text-sm font-medium text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-45"
              onClick={onReject}
            >
              <XCircleIcon className="size-4" aria-hidden="true" />
              拒绝行动
            </button>
          )}
          {selected.primaryActionLabel && (
            <button
              type="button"
              disabled={isSubmitting || !actorAvailable}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#252522] px-5 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:bg-[#d9d9d5] disabled:text-[#888882] sm:ml-auto"
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
                <PlayIcon className="size-4" aria-hidden="true" />
              )}
              {isSubmitting ? "正在提交" : selected.primaryActionLabel}
            </button>
          )}
        </div>
        <p className="mt-3 text-[11px] leading-5 text-[#85857e]">
          {!actorAvailable
            ? "当前没有可审计操作人，审批、执行和回滚保持禁用。"
            : "操作会创建可审计 Run 和真实执行产物；相同幂等键会安全返回既有结果。"}
        </p>
      </div>
    </article>
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
        sideBorder && "border-t border-black/[0.07] lg:border-t-0 lg:border-l",
      )}
    >
      <h3 className="mb-3 text-sm font-semibold text-[#33332f]">{title}</h3>
      {children}
    </section>
  );
}

function DefinitionList({
  rows,
}: {
  rows: Array<{ label: string; value: string }>;
}) {
  return (
    <dl className="overflow-hidden rounded-xl border border-black/[0.08] bg-white text-xs">
      {rows.map((row) => (
        <DefinitionRow key={row.label} label={row.label} value={row.value} />
      ))}
    </dl>
  );
}

function DefinitionRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-3 border-b border-black/[0.06] px-3 py-3 last:border-b-0 sm:grid-cols-[120px_minmax(0,1fr)]">
      <dt className="font-medium text-[#555550]">{label}</dt>
      <dd
        className={cn(
          "min-w-0 text-[#5f5f59]",
          mono && "font-mono text-[11px] break-all",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function StatusChip({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "status" | "risk";
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-md border px-2 py-1 text-[10px] font-medium whitespace-nowrap",
        tone === "neutral" && "border-black/[0.08] bg-[#fafaf8] text-[#6f6f69]",
        tone === "status" && "border-blue-200 bg-blue-50 text-blue-700",
        tone === "risk" && "border-amber-200 bg-amber-50 text-amber-700",
      )}
    >
      {children}
    </span>
  );
}

function ActionEmptyState() {
  return (
    <div className="mt-8 flex min-h-[38vh] flex-col items-center justify-center rounded-2xl border border-dashed border-black/[0.12] px-6 text-center">
      <ShieldCheckIcon className="size-6 text-[#777771]" aria-hidden="true" />
      <h2 className="mt-4 text-base font-semibold text-[#353530]">
        还没有候选行动
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#777771]">
        调查结论满足证据和策略门槛后，候选行动才会出现在这里。
      </p>
    </div>
  );
}

function FilteredEmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-black/[0.12] px-5 py-10 text-center text-sm text-[#777771]">
      当前筛选下没有行动记录。
    </div>
  );
}

function actionErrorMessage(error: unknown): string {
  if (error instanceof CommerceApiError) {
    if (error.code === "workspace_missing")
      return "当前工作区不可用，无法读取行动。";
    if (error.status === 409) return "行动状态已经变化，请刷新后再试。";
    if (error.status === 503) return "当前依赖服务不可用，本次操作没有执行。";
    if (error.code === "invalid_response")
      return "行动数据未通过前端合同校验。";
  }
  return "行动请求失败，本次操作没有被视为成功。";
}
