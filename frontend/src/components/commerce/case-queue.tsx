"use client";

import {
  ArchiveIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  Clock3Icon,
  DatabaseIcon,
  InboxIcon,
  PlusIcon,
  SearchIcon,
  XIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildCommerceCaseCreateOptions,
  buildCommerceCaseQueueViewModel,
  CommerceApiError,
  createCommerceExplicitCase,
  loadCommerceDataInboxSnapshot,
  validateCommerceExplicitCaseDraft,
  type CommerceCase,
  type CommerceCaseCreateOptions,
  type CommerceCaseQueueFilter,
  type CommerceCaseQueueItemViewModel,
  type CommerceCaseQueueViewModel,
  type CommerceDataInboxSnapshot,
  type CommerceExplicitCaseDraft,
  type CommerceExplicitCasePath,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

interface CommerceCaseQueueProps {
  workspaceId: string | null;
  cases: CommerceCase[];
  refreshSignal?: number;
  preferredPath?: string | null;
  onPreferredPathConsumed?: () => void;
  onOpenCase: (caseId: string) => void;
  onOpenDataInbox?: () => void;
}

export function CommerceCaseQueue({
  workspaceId,
  cases,
  refreshSignal = 0,
  preferredPath = null,
  onPreferredPathConsumed,
  onOpenCase,
  onOpenDataInbox,
}: CommerceCaseQueueProps) {
  const [filter, setFilter] = useState<CommerceCaseQueueFilter>("all");
  const [query, setQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(Boolean(preferredPath));
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createNotice, setCreateNotice] = useState<string | null>(null);
  const [createOptionsLoading, setCreateOptionsLoading] = useState(
    Boolean(workspaceId),
  );
  const [dataSnapshot, setDataSnapshot] =
    useState<CommerceDataInboxSnapshot | null>(null);

  useEffect(() => {
    if (!workspaceId) return;
    const controller = new AbortController();
    setCreateOptionsLoading(true);
    setCreateError(null);
    void loadCommerceDataInboxSnapshot({
      workspaceId,
      signal: controller.signal,
    })
      .then(setDataSnapshot)
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError")
          return;
        setCreateError(projectCreateLoadError(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setCreateOptionsLoading(false);
      });
    return () => controller.abort();
  }, [refreshSignal, workspaceId]);

  const viewModel = useMemo(
    () => buildCommerceCaseQueueViewModel(cases, { filter, query }),
    [cases, filter, query],
  );
  const createOptions = useMemo(
    () =>
      dataSnapshot
        ? buildCommerceCaseCreateOptions(dataSnapshot, preferredPath)
        : null,
    [dataSnapshot, preferredPath],
  );

  const createCase = async (draft: CommerceExplicitCaseDraft) => {
    if (!workspaceId || !createOptions) return;
    setCreating(true);
    setCreateError(null);
    setCreateNotice(null);
    try {
      const result = await createCommerceExplicitCase({
        workspaceId,
        datasetId: createOptions.datasetId,
        sellerId: draft.sellerId,
        baselineWindow: {
          start: withSeconds(draft.baselineStart),
          end: withSeconds(draft.baselineEnd),
        },
        currentWindow: {
          start: withSeconds(draft.currentStart),
          end: withSeconds(draft.currentEnd),
        },
        requestedPaths: draft.requestedPaths,
        peerPolicy: draft.requestedPaths.includes("seller_peer")
          ? {
              productCategory: draft.peerProductCategory,
              minOrdersPerSeller: draft.peerMinOrders,
              matchSellerState: draft.matchSellerState,
            }
          : null,
      });
      setCreateNotice("案例已创建，正在打开真实案例详情。");
      setCreateOpen(false);
      onPreferredPathConsumed?.();
      onOpenCase(result.case.id);
    } catch (cause) {
      setCreateError(projectCreateError(cause));
    } finally {
      setCreating(false);
    }
  };

  return (
    <CommerceCaseQueueView
      viewModel={viewModel}
      filter={filter}
      query={query}
      creating={creating}
      createOpen={createOpen}
      createError={createError}
      createNotice={createNotice}
      createOptions={createOptions}
      createOptionsLoading={createOptionsLoading}
      onFilterChange={setFilter}
      onQueryChange={setQuery}
      onOpenCase={onOpenCase}
      onOpenCreate={() => {
        setCreateError(null);
        setCreateNotice(null);
        setCreateOpen(true);
      }}
      onCloseCreate={() => {
        setCreateOpen(false);
        onPreferredPathConsumed?.();
      }}
      onCreateCase={createCase}
      onOpenDataInbox={onOpenDataInbox}
    />
  );
}

interface CommerceCaseQueueViewProps {
  viewModel: CommerceCaseQueueViewModel;
  filter: CommerceCaseQueueFilter;
  query: string;
  creating: boolean;
  createOpen: boolean;
  createError: string | null;
  createNotice: string | null;
  createOptions: CommerceCaseCreateOptions | null;
  createOptionsLoading: boolean;
  onFilterChange: (filter: CommerceCaseQueueFilter) => void;
  onQueryChange: (query: string) => void;
  onOpenCase: (caseId: string) => void;
  onOpenCreate: () => void;
  onCloseCreate: () => void;
  onCreateCase: (draft: CommerceExplicitCaseDraft) => void | Promise<void>;
  onOpenDataInbox?: () => void;
}

export function CommerceCaseQueueView({
  viewModel,
  filter,
  query,
  creating,
  createOpen,
  createError,
  createNotice,
  createOptions,
  createOptionsLoading,
  onFilterChange,
  onQueryChange,
  onOpenCase,
  onOpenCreate,
  onCloseCreate,
  onCreateCase,
  onOpenDataInbox,
}: CommerceCaseQueueViewProps) {
  return (
    <div className="min-h-full bg-white px-5 pt-6 pb-16 sm:px-8 lg:px-9">
      <div className="mx-auto max-w-[920px]">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold tracking-[0.16em] text-[#8a8a82] uppercase">
              案例队列
            </p>
            <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.035em] text-[#242421] sm:text-[32px]">
              {viewModel.title}
            </h1>
            <p className="mt-2 max-w-[680px] text-sm leading-6 text-[#6f6f69]">
              {viewModel.subtitle}
            </p>
          </div>
          <button
            type="button"
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={onOpenCreate}
          >
            <PlusIcon className="size-4" aria-hidden="true" />
            创建案例
          </button>
        </div>

        {createNotice && (
          <div
            className="mt-5 rounded-xl border border-[#dce5dc] bg-[#f5faf5] px-4 py-3 text-sm text-[#315338]"
            role="status"
          >
            {createNotice}
          </div>
        )}

        <div className="mt-8 border-y border-black/[0.07] py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div
              className="flex gap-2 overflow-x-auto pb-1 lg:pb-0"
              aria-label="案例状态筛选"
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
            <label className="flex min-h-10 w-full items-center gap-2 rounded-lg border border-black/[0.09] bg-white px-3 text-sm lg:w-[260px]">
              <SearchIcon
                className="size-4 shrink-0 text-[#777771]"
                aria-hidden="true"
              />
              <span className="sr-only">搜索案例</span>
              <input
                type="search"
                value={query}
                placeholder="搜索案例"
                className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#9a9a94]"
                onChange={(event) => onQueryChange(event.target.value)}
              />
            </label>
          </div>
        </div>

        {viewModel.status === "empty" ? (
          <CaseQueueEmptyState onOpenCreate={onOpenCreate} />
        ) : viewModel.resultCount === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-black/[0.12] px-6 py-14 text-center">
            <SearchIcon
              className="mx-auto size-6 text-[#777771]"
              aria-hidden="true"
            />
            <h2 className="mt-4 text-base font-semibold text-[#353530]">
              没有符合筛选条件的案例
            </h2>
            <p className="mt-2 text-sm text-[#777771]">
              调整状态或关键词后再查看。
            </p>
          </div>
        ) : (
          <div className="mt-8 space-y-9">
            <CaseQueueSection
              title="需要你处理"
              icon={InboxIcon}
              items={viewModel.attentionItems}
              onOpenCase={onOpenCase}
            />
            <CaseQueueSection
              title="持续跟踪"
              icon={Clock3Icon}
              items={viewModel.trackingItems}
              onOpenCase={onOpenCase}
            />
            <CaseQueueSection
              title="已结束"
              icon={ArchiveIcon}
              items={viewModel.closedItems}
              onOpenCase={onOpenCase}
            />
          </div>
        )}
      </div>

      {createOpen && (
        <CommerceCaseCreatePanel
          key={`${createOptions?.datasetId ?? "empty"}:${createOptions?.pathOptions
            .filter((item) => item.selected)
            .map((item) => item.value)
            .join(",")}`}
          options={createOptions}
          optionsLoading={createOptionsLoading}
          creating={creating}
          error={createError}
          onClose={onCloseCreate}
          onCreateCase={onCreateCase}
          onOpenDataInbox={onOpenDataInbox}
        />
      )}
    </div>
  );
}

function CaseQueueSection({
  title,
  icon: Icon,
  items,
  onOpenCase,
}: {
  title: string;
  icon: typeof InboxIcon;
  items: CommerceCaseQueueItemViewModel[];
  onOpenCase: (caseId: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby={`case-queue-${title}`}>
      <h2
        id={`case-queue-${title}`}
        className="flex items-center gap-2 text-sm font-semibold text-[#2d2d29]"
      >
        <Icon className="size-4 text-[#777771]" aria-hidden="true" />
        {title}
      </h2>
      <div className="mt-3 overflow-hidden rounded-xl border border-black/[0.08]">
        {items.map((item) => (
          <CaseQueueRow key={item.id} item={item} onOpenCase={onOpenCase} />
        ))}
      </div>
    </section>
  );
}

function CaseQueueRow({
  item,
  onOpenCase,
}: {
  item: CommerceCaseQueueItemViewModel;
  onOpenCase: (caseId: string) => void;
}) {
  return (
    <article className="grid gap-4 border-b border-black/[0.06] px-4 py-4 last:border-b-0 lg:grid-cols-[minmax(170px,0.8fr)_minmax(260px,1.5fr)_104px] lg:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-2.5">
          <span
            className={cn(
              "size-2.5 shrink-0 rounded-full",
              item.severity === "critical" || item.severity === "high"
                ? "bg-red-500"
                : item.severity === "medium"
                  ? "bg-amber-500"
                  : "bg-emerald-500",
            )}
            aria-hidden="true"
          />
          <h3 className="truncate text-sm font-semibold text-[#343430]">
            {item.title}
          </h3>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5 pl-5">
          <StatusChip tone={statusTone(item.status)}>
            {item.statusLabel}
          </StatusChip>
          <StatusChip tone={severityTone(item.severity)}>
            {item.severityLabel}
          </StatusChip>
        </div>
      </div>
      <div className="min-w-0 pl-5 lg:pl-0">
        <p className="text-sm leading-6 text-[#5f5f59]">{item.summary}</p>
        <p className="mt-1 text-[11px] text-[#92928b]">
          更新于 {item.updatedLabel}
        </p>
      </div>
      <button
        type="button"
        className="ml-5 inline-flex min-h-10 items-center justify-center gap-1 rounded-lg border border-black/[0.1] px-3 text-xs font-medium text-[#454540] hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-offset-2 lg:ml-0"
        onClick={() => onOpenCase(item.id)}
      >
        {item.actionLabel}
        <ChevronRightIcon className="size-3.5" aria-hidden="true" />
      </button>
    </article>
  );
}

function StatusChip({
  tone,
  children,
}: {
  tone: "neutral" | "danger" | "warning" | "success";
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "rounded-md border px-2 py-1 text-[11px] font-medium",
        tone === "neutral" && "border-black/[0.08] bg-[#fafaf8] text-[#707069]",
        tone === "danger" && "border-red-200 bg-red-50 text-red-700",
        tone === "warning" && "border-[#ead9b2] bg-[#fffaf0] text-[#8b641e]",
        tone === "success" && "border-[#cfe1d1] bg-[#f7fbf7] text-[#3d6a43]",
      )}
    >
      {children}
    </span>
  );
}

function CaseQueueEmptyState({ onOpenCreate }: { onOpenCreate: () => void }) {
  return (
    <div className="mt-12 flex min-h-[38vh] flex-col items-center justify-center rounded-2xl border border-dashed border-black/[0.12] px-6 text-center">
      <InboxIcon className="size-6 text-[#777771]" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold text-[#353530]">
        还没有经营案例
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#777771]">
        先检查数据能力，再创建范围明确、可追溯的经营诊断案例。
      </p>
      <button
        type="button"
        className="mt-5 min-h-11 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black"
        onClick={onOpenCreate}
      >
        创建第一个案例
      </button>
    </div>
  );
}

function CommerceCaseCreatePanel({
  options,
  optionsLoading,
  creating,
  error,
  onClose,
  onCreateCase,
  onOpenDataInbox,
}: {
  options: CommerceCaseCreateOptions | null;
  optionsLoading: boolean;
  creating: boolean;
  error: string | null;
  onClose: () => void;
  onCreateCase: (draft: CommerceExplicitCaseDraft) => void | Promise<void>;
  onOpenDataInbox?: () => void;
}) {
  const [sellerId, setSellerId] = useState(options?.sellerSuggestions[0] ?? "");
  const [baselineStart, setBaselineStart] = useState("");
  const [baselineEnd, setBaselineEnd] = useState("");
  const [currentStart, setCurrentStart] = useState("");
  const [currentEnd, setCurrentEnd] = useState("");
  const [requestedPaths, setRequestedPaths] = useState<
    CommerceExplicitCasePath[]
  >(
    options?.pathOptions
      .filter((item) => item.selected)
      .map((item) => item.value) ?? [],
  );
  const [peerProductCategory, setPeerProductCategory] = useState("");
  const [peerMinOrders, setPeerMinOrders] = useState(20);
  const [matchSellerState, setMatchSellerState] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const draft: CommerceExplicitCaseDraft = {
      sellerId,
      baselineStart,
      baselineEnd,
      currentStart,
      currentEnd,
      requestedPaths,
      peerProductCategory,
      peerMinOrders,
      matchSellerState,
    };
    const nextError = validateCommerceExplicitCaseDraft(draft);
    setValidationError(nextError);
    if (!nextError) void onCreateCase(draft);
  };

  return (
    <div className="fixed inset-0 z-[60] flex justify-end bg-black/20 backdrop-blur-[1px]">
      <button
        type="button"
        aria-label="关闭创建案例"
        className="absolute inset-0"
        onClick={onClose}
      />
      <aside
        aria-label="创建案例"
        className="relative h-full w-full max-w-[520px] overflow-y-auto border-l border-black/[0.08] bg-white shadow-2xl"
      >
        <div className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-black/[0.07] bg-white/95 px-5 backdrop-blur">
          <div>
            <p className="text-sm font-semibold text-[#292925]">创建案例</p>
            <p className="mt-0.5 text-[11px] text-[#85857e]">
              明确范围后才会持久化案例
            </p>
          </div>
          <button
            type="button"
            aria-label="关闭创建案例面板"
            className="rounded-lg p-2 text-[#666660] hover:bg-black/5"
            onClick={onClose}
          >
            <XIcon className="size-4" aria-hidden="true" />
          </button>
        </div>

        {optionsLoading ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center px-8 text-center">
            <DatabaseIcon
              className="size-6 text-[#777771]"
              aria-hidden="true"
            />
            <h2 className="mt-4 text-base font-semibold text-[#353530]">
              正在读取创建案例所需的数据能力
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#777771]">
              系统正在恢复最新数据批次与数据能力，不会在读取完成前猜测可用路径。
            </p>
          </div>
        ) : !options ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center px-8 text-center">
            <DatabaseIcon
              className="size-6 text-[#777771]"
              aria-hidden="true"
            />
            <h2 className="mt-4 text-base font-semibold text-[#353530]">
              还没有可用于创建案例的数据批次
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#777771]">
              先接入数据并完成能力检查，再选择经营主体和分析窗口。
            </p>
            {error && (
              <p
                className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                role="alert"
              >
                {error}
              </p>
            )}
            {onOpenDataInbox && (
              <button
                type="button"
                className="mt-5 min-h-11 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white"
                onClick={onOpenDataInbox}
              >
                前往数据接入
              </button>
            )}
          </div>
        ) : (
          <form className="space-y-7 px-5 py-6 sm:px-6" onSubmit={submit}>
            <section>
              <h2 className="text-xs font-semibold text-[#3b3b36]">
                数据与经营主体
              </h2>
              <div className="mt-3 space-y-4 rounded-xl border border-black/[0.08] bg-[#fafaf8] p-4">
                <div>
                  <p className="text-[11px] text-[#85857e]">当前数据批次</p>
                  <p className="mt-1 text-sm font-medium text-[#3f3f3a]">
                    {options.datasetLabel}
                  </p>
                </div>
                <label className="block text-xs font-medium text-[#555550]">
                  经营主体（卖家编号）
                  <input
                    type="text"
                    list="commerce-seller-suggestions"
                    value={sellerId}
                    className="mt-2 min-h-11 w-full rounded-lg border border-black/[0.1] bg-white px-3 text-sm outline-none focus:border-black/30"
                    placeholder="输入数据中存在的卖家编号"
                    onChange={(event) => setSellerId(event.target.value)}
                  />
                  <datalist id="commerce-seller-suggestions">
                    {options.sellerSuggestions.map((seller) => (
                      <option key={seller} value={seller} />
                    ))}
                  </datalist>
                </label>
              </div>
            </section>

            <section>
              <h2 className="text-xs font-semibold text-[#3b3b36]">分析窗口</h2>
              <div className="mt-3 grid gap-4 rounded-xl border border-black/[0.08] p-4 sm:grid-cols-2">
                <DateTimeField
                  label="基线开始"
                  value={baselineStart}
                  onChange={setBaselineStart}
                />
                <DateTimeField
                  label="基线结束"
                  value={baselineEnd}
                  onChange={setBaselineEnd}
                />
                <DateTimeField
                  label="当前开始"
                  value={currentStart}
                  onChange={setCurrentStart}
                />
                <DateTimeField
                  label="当前结束"
                  value={currentEnd}
                  onChange={setCurrentEnd}
                />
              </div>
            </section>

            <section>
              <h2 className="text-xs font-semibold text-[#3b3b36]">分析路径</h2>
              <div className="mt-3 space-y-2">
                {options.pathOptions.map((path) => (
                  <label
                    key={path.value}
                    className={cn(
                      "flex min-h-12 items-center justify-between gap-3 rounded-xl border px-4 py-3",
                      path.disabled
                        ? "cursor-not-allowed border-black/[0.06] bg-[#fafaf8] text-[#92928b]"
                        : "border-black/[0.09] text-[#454540] hover:bg-black/[0.02]",
                    )}
                  >
                    <span className="flex items-center gap-3 text-sm font-medium">
                      <input
                        type="checkbox"
                        checked={requestedPaths.includes(path.value)}
                        disabled={path.disabled}
                        onChange={(event) =>
                          setRequestedPaths((current) =>
                            event.target.checked
                              ? [...current, path.value]
                              : current.filter((item) => item !== path.value),
                          )
                        }
                      />
                      {path.label}
                    </span>
                    <span className="text-[11px]">{path.statusLabel}</span>
                  </label>
                ))}
              </div>
            </section>

            {requestedPaths.includes("seller_peer") && (
              <section>
                <h2 className="text-xs font-semibold text-[#3b3b36]">
                  卖家对标口径
                </h2>
                <div className="mt-3 space-y-4 rounded-xl border border-[#ead9b2] bg-[#fffaf0] p-4">
                  <label className="block text-xs font-medium text-[#6f5524]">
                    商品类目
                    <input
                      type="text"
                      value={peerProductCategory}
                      className="mt-2 min-h-11 w-full rounded-lg border border-[#e0cfaa] bg-white px-3 text-sm outline-none"
                      onChange={(event) =>
                        setPeerProductCategory(event.target.value)
                      }
                    />
                  </label>
                  <label className="block text-xs font-medium text-[#6f5524]">
                    每个同类卖家的最小订单数
                    <input
                      type="number"
                      min={2}
                      value={peerMinOrders}
                      className="mt-2 min-h-11 w-full rounded-lg border border-[#e0cfaa] bg-white px-3 text-sm outline-none"
                      onChange={(event) =>
                        setPeerMinOrders(Number(event.target.value))
                      }
                    />
                  </label>
                  <label className="flex items-center gap-2 text-xs text-[#6f5524]">
                    <input
                      type="checkbox"
                      checked={matchSellerState}
                      onChange={(event) =>
                        setMatchSellerState(event.target.checked)
                      }
                    />
                    同时匹配卖家所在州
                  </label>
                </div>
              </section>
            )}

            {(validationError ?? error) && (
              <div
                className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                role="alert"
              >
                <CircleAlertIcon
                  className="mt-0.5 size-4 shrink-0"
                  aria-hidden="true"
                />
                {validationError ?? error}
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 border-t border-black/[0.07] pt-5 sm:flex-row sm:justify-end">
              <button
                type="button"
                className="min-h-11 rounded-lg border border-black/[0.1] px-4 text-sm text-[#555550] hover:bg-black/[0.035]"
                onClick={onClose}
              >
                取消
              </button>
              <button
                type="submit"
                disabled={creating}
                className="min-h-11 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black disabled:opacity-50"
              >
                {creating ? "正在创建" : "创建并打开案例"}
              </button>
            </div>
          </form>
        )}
      </aside>
    </div>
  );
}

function DateTimeField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs font-medium text-[#555550]">
      {label}
      <input
        type="text"
        inputMode="numeric"
        placeholder="2026-05-01 00:00"
        value={value}
        className="mt-2 min-h-11 w-full rounded-lg border border-black/[0.1] bg-white px-3 text-xs outline-none focus:border-black/30"
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function statusTone(status: string) {
  if (status === "awaiting_data" || status === "awaiting_approval") {
    return "warning" as const;
  }
  if (status === "monitoring" || status === "resolved") {
    return "success" as const;
  }
  if (status === "blocked") return "danger" as const;
  return "neutral" as const;
}

function severityTone(severity: string) {
  if (severity === "critical" || severity === "high") return "danger" as const;
  if (severity === "medium") return "warning" as const;
  return "neutral" as const;
}

function withSeconds(value: string): string {
  const normalized = value.trim().replace(" ", "T");
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/u.test(normalized)
    ? `${normalized}:00`
    : normalized;
}

function projectCreateLoadError(cause: unknown): string {
  if (cause instanceof CommerceApiError && cause.status === 409) {
    return "数据批次完整性检查未通过，当前不能创建案例。";
  }
  return "暂时无法读取创建案例所需的数据能力。";
}

function projectCreateError(cause: unknown): string {
  if (cause instanceof CommerceApiError && cause.status === 400) {
    return "创建范围未通过校验，请确认卖家、时间窗口和分析路径。";
  }
  if (cause instanceof CommerceApiError && cause.status === 404) {
    return "当前数据批次已不存在，请返回数据接入重新选择。";
  }
  return "案例暂时无法创建，系统没有启动调查或伪造案例。";
}
