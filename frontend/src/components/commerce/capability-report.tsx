"use client";

import {
  BanIcon,
  CheckCircle2Icon,
  CircleAlertIcon,
  DatabaseIcon,
  EyeIcon,
  EyeOffIcon,
  StarIcon,
  TruckIcon,
  UsersRoundIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildCommerceCapabilityReportViewModel,
  CommerceApiError,
  loadCommerceDataInboxSnapshot,
  type CommerceCapabilityPathViewModel,
  type CommerceCapabilityReportViewModel,
  type CommerceDataInboxSnapshot,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

interface CommerceCapabilityReportProps {
  workspaceId: string | null;
  refreshSignal?: number;
  onOpenDataInbox?: () => void;
  onOpenCases?: () => void;
  onCreateCase?: (path: CommerceCapabilityPathViewModel) => void;
}

type CapabilityError = {
  title: string;
  description: string;
};

export function CommerceCapabilityReport({
  workspaceId,
  refreshSignal = 0,
  onOpenDataInbox,
  onOpenCases,
  onCreateCase,
}: CommerceCapabilityReportProps) {
  const [snapshot, setSnapshot] = useState<CommerceDataInboxSnapshot | null>(
    null,
  );
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<CapabilityError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) return;
    const controller = new AbortController();
    setError(null);
    void loadCommerceDataInboxSnapshot({
      workspaceId,
      signal: controller.signal,
    })
      .then(setSnapshot)
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError")
          return;
        setError(projectCapabilityError(cause));
      });
    return () => controller.abort();
  }, [refreshKey, refreshSignal, workspaceId]);

  const viewModel = useMemo(
    () =>
      buildCommerceCapabilityReportViewModel(
        snapshot ?? {
          workspaceId: workspaceId ?? "",
          datasets: [],
          selectedDataset: null,
        },
      ),
    [snapshot, workspaceId],
  );

  return (
    <CommerceCapabilityReportView
      viewModel={viewModel}
      error={error}
      notice={notice}
      onRetry={() => setRefreshKey((value) => value + 1)}
      onOpenDataInbox={onOpenDataInbox}
      onOpenCases={onOpenCases}
      onCreateCase={(path) => {
        if (onCreateCase) {
          onCreateCase(path);
          return;
        }
        setNotice(
          `${path.label}已满足当前数据能力要求；创建案例需要先进入案例队列补充分析窗口和经营主体。`,
        );
      }}
    />
  );
}

interface CommerceCapabilityReportViewProps {
  viewModel: CommerceCapabilityReportViewModel;
  error: CapabilityError | null;
  notice: string | null;
  onRetry: () => void;
  onOpenDataInbox?: () => void;
  onOpenCases?: () => void;
  onCreateCase: (path: CommerceCapabilityPathViewModel) => void;
}

export function CommerceCapabilityReportView({
  viewModel,
  error,
  notice,
  onRetry,
  onOpenDataInbox,
  onOpenCases,
  onCreateCase,
}: CommerceCapabilityReportViewProps) {
  return (
    <div className="min-h-full bg-white px-5 pt-6 pb-16 sm:px-8 lg:px-9">
      <div className="mx-auto max-w-[920px]">
        <div>
          <p className="text-[11px] font-semibold tracking-[0.16em] text-[#8a8a82] uppercase">
            数据能力
          </p>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.035em] text-[#242421] sm:text-[32px]">
            {viewModel.title}
          </h1>
          <p className="mt-2 max-w-[740px] text-sm leading-6 text-[#6f6f69]">
            {viewModel.subtitle}
          </p>
          {viewModel.metadataLabel && (
            <p className="mt-3 text-xs text-[#878780]">
              {viewModel.metadataLabel}
            </p>
          )}
        </div>

        {error && (
          <div
            className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-950"
            role="alert"
          >
            <div>
              <p className="font-medium">{error.title}</p>
              <p className="mt-1 text-xs leading-5 text-red-800">
                {error.description}
              </p>
            </div>
            <button
              type="button"
              className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium hover:bg-red-100"
              onClick={onRetry}
            >
              重试
            </button>
          </div>
        )}

        {notice && (
          <div
            className="mt-5 rounded-xl border border-[#dce5dc] bg-[#f5faf5] px-4 py-3 text-sm text-[#315338]"
            role="status"
          >
            {notice}
          </div>
        )}

        {viewModel.status === "empty" ? (
          <CapabilityEmptyState onOpenDataInbox={onOpenDataInbox} />
        ) : (
          <>
            <section
              className="mt-8"
              aria-labelledby="capability-conclusion-heading"
            >
              <h2
                id="capability-conclusion-heading"
                className="text-sm font-semibold text-[#2d2d29]"
              >
                能力结论
              </h2>
              <div className="mt-3 grid gap-3 lg:grid-cols-3">
                {viewModel.paths.map((path) => (
                  <CapabilitySummaryCard key={path.name} path={path} />
                ))}
              </div>
            </section>

            <section
              className="mt-8"
              aria-labelledby="capability-paths-heading"
            >
              <h2
                id="capability-paths-heading"
                className="text-sm font-semibold text-[#2d2d29]"
              >
                可用分析路径
              </h2>
              <div className="mt-3 overflow-hidden rounded-xl border border-black/[0.08]">
                <div className="hidden grid-cols-[1.1fr_0.85fr_1.45fr_92px] gap-4 border-b border-black/[0.07] bg-[#fafaf8] px-4 py-3 text-[11px] font-medium text-[#85857e] lg:grid">
                  <span>分析路径</span>
                  <span>状态</span>
                  <span>所需语义（已确认字段）</span>
                  <span className="text-right">操作</span>
                </div>
                {viewModel.paths.map((path) => (
                  <CapabilityPathRow
                    key={path.name}
                    path={path}
                    onCreateCase={onCreateCase}
                  />
                ))}
              </div>
            </section>

            <section
              className="mt-8"
              aria-labelledby="capability-boundary-heading"
            >
              <h2
                id="capability-boundary-heading"
                className="text-sm font-semibold text-[#2d2d29]"
              >
                数据边界
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <BoundaryCard
                  tone="observed"
                  title="已观察"
                  items={viewModel.observedLabels}
                />
                <BoundaryCard
                  tone="unobserved"
                  title="未观察"
                  items={viewModel.notObservedLabels}
                />
              </div>
            </section>

            <section
              className="mt-8"
              aria-labelledby="capability-review-heading"
            >
              <h2
                id="capability-review-heading"
                className="text-sm font-semibold text-[#2d2d29]"
              >
                需要补充或确认
              </h2>
              {viewModel.reviewItems.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {viewModel.reviewItems.map((item) => (
                    <div
                      key={`${item.tableName}.${item.columnName}`}
                      className="flex flex-col gap-3 rounded-xl border border-[#ead9b2] bg-[#fffaf0] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="flex min-w-0 items-center gap-3 text-sm text-[#775b25]">
                        <CircleAlertIcon
                          className="size-4 shrink-0 text-[#a8751d]"
                          aria-hidden="true"
                        />
                        <span className="truncate font-mono text-xs sm:text-sm">
                          {item.tableName}.{item.columnName}
                        </span>
                        <span className="text-[#b9a276]">→</span>
                        <span className="shrink-0 font-sans">
                          {item.semanticLabel}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="min-h-10 shrink-0 rounded-lg border border-[#e0cfaa] px-3 text-sm font-medium text-[#795d27] hover:bg-white"
                        onClick={onOpenDataInbox}
                      >
                        返回数据接入确认
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-3 rounded-xl border border-[#dce8dc] bg-[#f5faf5] px-4 py-3 text-sm text-[#315338]">
                  <span className="inline-flex items-center gap-2 font-medium">
                    <CheckCircle2Icon className="size-4" aria-hidden="true" />
                    当前没有待确认字段
                  </span>
                </div>
              )}
              <p className="mt-3 rounded-xl border border-black/[0.07] bg-[#fafaf8] px-4 py-3 text-xs leading-5 text-[#777771]">
                未观察字段不会被推断为零，也不会生成对应经营结论。
              </p>
            </section>

            {onOpenCases && (
              <button
                type="button"
                className="mt-8 text-xs font-medium text-[#707069] underline decoration-black/20 underline-offset-4 hover:text-[#252522]"
                onClick={onOpenCases}
              >
                返回案例队列
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function CapabilitySummaryCard({
  path,
}: {
  path: CommerceCapabilityPathViewModel;
}) {
  const Icon =
    path.status === "available"
      ? CheckCircle2Icon
      : path.status === "partial"
        ? CircleAlertIcon
        : BanIcon;
  return (
    <article
      className={cn(
        "rounded-xl border px-4 py-4",
        path.status === "available" && "border-[#cfe1d1] bg-[#f7fbf7]",
        path.status === "partial" && "border-[#ead9b2] bg-[#fffaf0]",
        path.status === "unavailable" && "border-black/[0.12] bg-[#fafaf8]",
      )}
    >
      <div className="flex items-start gap-3">
        <Icon
          className={cn(
            "mt-0.5 size-5 shrink-0",
            path.status === "available" && "text-[#4f7754]",
            path.status === "partial" && "text-[#a8751d]",
            path.status === "unavailable" && "text-[#777771]",
          )}
          aria-hidden="true"
        />
        <div className="min-w-0">
          <p
            className={cn(
              "text-sm font-semibold",
              path.status === "available" && "text-[#3d6a43]",
              path.status === "partial" && "text-[#8b641e]",
              path.status === "unavailable" && "text-[#555550]",
            )}
          >
            {path.statusLabel}
          </p>
          <p className="mt-2 text-sm font-medium text-[#45453f]">
            {path.label}
          </p>
          <p className="mt-1 text-xs leading-5 text-[#777771]">
            {path.statusDescription}
          </p>
        </div>
      </div>
    </article>
  );
}

function CapabilityPathRow({
  path,
  onCreateCase,
}: {
  path: CommerceCapabilityPathViewModel;
  onCreateCase: (path: CommerceCapabilityPathViewModel) => void;
}) {
  const Icon =
    path.name === "fulfillment_diagnosis"
      ? TruckIcon
      : path.name === "review_experience"
        ? StarIcon
        : UsersRoundIcon;
  return (
    <div className="grid gap-3 border-b border-black/[0.06] px-4 py-4 last:border-b-0 lg:grid-cols-[1.1fr_0.85fr_1.45fr_92px] lg:items-center lg:gap-4">
      <div className="flex min-w-0 items-start gap-3">
        <Icon
          className="mt-0.5 size-5 shrink-0 text-[#60605a]"
          aria-hidden="true"
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#3b3b36]">{path.label}</p>
          <p className="mt-1 text-xs leading-5 text-[#777771]">
            {path.description}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs font-medium">
        {path.status === "available" ? (
          <CheckCircle2Icon
            className="size-4 text-[#4f7754]"
            aria-hidden="true"
          />
        ) : path.status === "partial" ? (
          <CircleAlertIcon
            className="size-4 text-[#a8751d]"
            aria-hidden="true"
          />
        ) : (
          <BanIcon className="size-4 text-[#777771]" aria-hidden="true" />
        )}
        <span
          className={cn(
            path.status === "available" && "text-[#4f7754]",
            path.status === "partial" && "text-[#a8751d]",
            path.status === "unavailable" && "text-[#777771]",
          )}
        >
          {path.statusLabel}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5 pl-8 lg:pl-0">
        {(path.availableFields.length > 0
          ? path.availableFields
          : path.missingFields
        )
          .slice(0, 6)
          .map((field) => (
            <span
              key={field}
              className={cn(
                "rounded-md border px-2 py-1 text-[11px]",
                path.availableFields.length > 0
                  ? "border-black/[0.08] bg-[#fafaf8] text-[#686862]"
                  : "border-black/[0.08] bg-[#f5f5f3] text-[#898983]",
              )}
            >
              {field}
            </span>
          ))}
        {path.reasonLabels.slice(0, 2).map((reason) => (
          <span
            key={reason}
            className="rounded-md border border-[#ead9b2] bg-[#fffaf0] px-2 py-1 text-[11px] text-[#8b641e]"
          >
            {reason}
          </span>
        ))}
      </div>
      <div className="flex justify-end">
        {path.canCreateCase ? (
          <button
            type="button"
            className={cn(
              "min-h-10 rounded-lg border px-3 text-xs font-medium",
              path.status === "available"
                ? "border-[#bfd8c2] text-[#3d6a43] hover:bg-[#f5faf5]"
                : "border-[#e0cfaa] text-[#8b641e] hover:bg-[#fffaf0]",
            )}
            onClick={() => onCreateCase(path)}
          >
            创建案例
          </button>
        ) : (
          <span className="px-3 text-sm text-[#8b8b85]">—</span>
        )}
      </div>
    </div>
  );
}

function BoundaryCard({
  tone,
  title,
  items,
}: {
  tone: "observed" | "unobserved";
  title: string;
  items: readonly string[];
}) {
  const observed = tone === "observed";
  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-3",
        observed
          ? "border-[#cfe1d1] bg-[#f7fbf7]"
          : "border-[#ead9b2] bg-[#fffaf0]",
      )}
    >
      <div className="flex items-start gap-3">
        {observed ? (
          <EyeIcon
            className="mt-0.5 size-4 shrink-0 text-[#4f7754]"
            aria-hidden="true"
          />
        ) : (
          <EyeOffIcon
            className="mt-0.5 size-4 shrink-0 text-[#a8751d]"
            aria-hidden="true"
          />
        )}
        <div>
          <p
            className={cn(
              "text-sm font-semibold",
              observed ? "text-[#3d6a43]" : "text-[#8b641e]",
            )}
          >
            {title}
          </p>
          <p className="mt-1 text-xs leading-5 text-[#777771]">
            {items.length > 0 ? items.join("、") : "暂无可确认字段"}
          </p>
        </div>
      </div>
    </div>
  );
}

function CapabilityEmptyState({
  onOpenDataInbox,
}: {
  onOpenDataInbox?: () => void;
}) {
  return (
    <div className="mt-12 flex min-h-[42vh] flex-col items-center justify-center rounded-2xl border border-dashed border-black/[0.12] px-6 text-center">
      <DatabaseIcon className="size-6 text-[#777771]" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold text-[#353530]">
        还没有可检查的数据批次
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#777771]">
        先接入经营数据并完成字段语义确认，系统才能给出可追溯的能力边界。
      </p>
      {onOpenDataInbox && (
        <button
          type="button"
          className="mt-5 min-h-11 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black"
          onClick={onOpenDataInbox}
        >
          前往数据接入
        </button>
      )}
    </div>
  );
}

function projectCapabilityError(cause: unknown): CapabilityError {
  if (cause instanceof CommerceApiError && cause.status === 409) {
    return {
      title: "数据批次需要重新检查",
      description:
        "来源或清单校验未通过，系统没有把不完整的数据投影为能力结论。",
    };
  }
  return {
    title: "数据能力暂时无法读取",
    description: "系统没有猜测当前批次的分析范围，请检查数据接入状态后重试。",
  };
}
