"use client";

import {
  BarChart3Icon,
  CheckCircle2Icon,
  ChevronRightIcon,
  CircleAlertIcon,
  FileTextIcon,
  HelpCircleIcon,
  SearchIcon,
  XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  filterCommerceEvidenceExplorerItems,
  type CommerceEvidenceExplorerItemViewModel,
  type CommerceEvidenceExplorerViewModel,
  type CommerceEvidenceFilter,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

export function CommerceEvidenceExplorer({
  viewModel,
}: {
  viewModel: CommerceEvidenceExplorerViewModel;
}) {
  const [filter, setFilter] = useState<CommerceEvidenceFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(
    viewModel.items[0]?.id ?? null,
  );
  const items = useMemo(
    () =>
      filterCommerceEvidenceExplorerItems(viewModel.items, { filter, query }),
    [filter, query, viewModel.items],
  );
  const selected =
    items.find((item) => item.id === selectedEvidenceId) ?? items[0] ?? null;

  return (
    <section className="mx-auto w-full max-w-[920px] py-6">
      <div>
        <h2 className="text-[24px] font-semibold tracking-[-0.025em] text-[#292925]">
          {viewModel.title}
        </h2>
        <p className="mt-2 max-w-[700px] text-sm leading-6 text-[#6f6f69]">
          {viewModel.subtitle}
        </p>
      </div>

      <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div
          className="flex gap-2 overflow-x-auto pb-1 lg:pb-0"
          aria-label="证据关系筛选"
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
              onClick={() => setFilter(item.value)}
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
          <span className="sr-only">搜索证据</span>
          <input
            type="search"
            value={query}
            placeholder="搜索证据"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#9a9a94]"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>

      {viewModel.items.length === 0 ? (
        <EvidenceEmptyState />
      ) : items.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-dashed border-black/[0.12] px-6 py-12 text-center">
          <SearchIcon
            className="mx-auto size-6 text-[#777771]"
            aria-hidden="true"
          />
          <h3 className="mt-4 text-base font-semibold text-[#353530]">
            没有符合条件的证据
          </h3>
          <p className="mt-2 text-sm text-[#777771]">
            调整关系筛选或关键词后再查看。
          </p>
        </div>
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(330px,0.92fr)]">
          <div className="space-y-2">
            {items.map((item) => {
              const active = item.id === selected?.id;
              return (
                <article
                  key={item.id}
                  className={cn(
                    "overflow-hidden rounded-xl border bg-white",
                    active
                      ? relationActiveBorder(item.relation)
                      : "border-black/[0.08]",
                  )}
                >
                  <button
                    type="button"
                    aria-pressed={active}
                    className="flex w-full items-start gap-3 px-4 py-4 text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                    onClick={() => setSelectedEvidenceId(item.id)}
                  >
                    <EvidenceRelationIcon item={item} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-sm leading-6 font-semibold text-[#343430]">
                          {item.summary}
                        </h3>
                        <span
                          className={cn(
                            "shrink-0 text-sm font-semibold",
                            relationTextColor(item.relation),
                          )}
                        >
                          {item.confidenceLabel}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <EvidenceChip relation={item.relation}>
                          {item.relationLabel}
                        </EvidenceChip>
                        <EvidenceChip>{item.typeLabel}</EvidenceChip>
                        <EvidenceChip>{item.semanticStatusLabel}</EvidenceChip>
                        <span className="ml-auto text-[11px] text-[#8a8a84]">
                          {item.referenceCountLabel}
                        </span>
                      </div>
                    </div>
                    <ChevronRightIcon
                      className={cn(
                        "mt-1 size-4 shrink-0 text-[#85857e] transition-transform motion-reduce:transition-none xl:block",
                        active && "rotate-90 xl:rotate-0",
                      )}
                      aria-hidden="true"
                    />
                  </button>
                  {active && (
                    <div className="border-t border-black/[0.06] px-4 py-4 xl:hidden">
                      <EvidenceDetail item={item} compact />
                    </div>
                  )}
                </article>
              );
            })}
          </div>

          {selected && (
            <div className="hidden xl:block">
              <div className="sticky top-4 rounded-xl border border-black/[0.08] bg-[#fcfcfa] p-5">
                <EvidenceDetail item={selected} />
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function EvidenceDetail({
  item,
  compact = false,
}: {
  item: CommerceEvidenceExplorerItemViewModel;
  compact?: boolean;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#33332f]">证据详情</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <EvidenceChip relation={item.relation}>
              {item.relationLabel}
            </EvidenceChip>
            <EvidenceChip>{item.semanticStatusLabel}</EvidenceChip>
          </div>
        </div>
        <code className="rounded-md border border-black/[0.07] bg-white px-2 py-1 text-[10px] text-[#777771]">
          {item.shortId}
        </code>
      </div>

      <DetailSection title="证据说明">
        <p className="text-sm leading-6 text-[#555550]">{item.summary}</p>
      </DetailSection>

      <DetailSection title="引用对象">
        {item.references.length > 0 ? (
          <div className="overflow-hidden rounded-lg border border-black/[0.08] bg-white">
            {item.references.map((reference) => (
              <div
                key={`${reference.kind}:${reference.id}`}
                className="flex items-start gap-3 border-b border-black/[0.06] px-3 py-3 last:border-b-0"
              >
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-[#f3f3f0] text-[#666660]">
                  {reference.kind === "metric" ? (
                    <BarChart3Icon className="size-3.5" aria-hidden="true" />
                  ) : (
                    <FileTextIcon className="size-3.5" aria-hidden="true" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-[#41413c]">
                    {reference.label}
                  </p>
                  <p className="mt-1 text-sm text-[#555550]">
                    {reference.valueLabel}
                  </p>
                  <p className="mt-1 text-[10px] text-[#92928b]">
                    {reference.metadataLabel}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-black/[0.1] px-3 py-3 text-xs leading-5 text-[#777771]">
            当前证据没有可展示的事实或指标引用。
          </p>
        )}
      </DetailSection>

      <DetailSection title="支持的判断">
        {item.hypotheses.length > 0 ? (
          <div className="space-y-2">
            {item.hypotheses.map((hypothesis) => (
              <div
                key={hypothesis.id}
                className="rounded-lg border border-black/[0.08] bg-white px-3 py-3"
              >
                <p className="text-xs leading-5 font-medium text-[#44443f]">
                  {hypothesis.label}
                </p>
                <p className="mt-1 text-[10px] text-[#85857e]">
                  {hypothesis.relationLabel} · {hypothesis.statusLabel}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs leading-5 text-[#777771]">
            当前没有与此证据直接关联的工作假设。
          </p>
        )}
      </DetailSection>

      <DetailSection title="证据边界" last={compact}>
        <div className="flex items-start gap-2 rounded-lg border border-black/[0.07] bg-[#f7f7f5] px-3 py-3">
          <CircleAlertIcon
            className="mt-0.5 size-4 shrink-0 text-[#777771]"
            aria-hidden="true"
          />
          <p className="text-xs leading-5 text-[#666660]">{item.boundary}</p>
        </div>
      </DetailSection>
    </div>
  );
}

function DetailSection({
  title,
  children,
  last = false,
}: {
  title: string;
  children: React.ReactNode;
  last?: boolean;
}) {
  return (
    <div className={cn("mt-5", last && "mb-1")}>
      <h4 className="mb-2 text-xs font-semibold text-[#3f3f3a]">{title}</h4>
      {children}
    </div>
  );
}

function EvidenceRelationIcon({
  item,
}: {
  item: CommerceEvidenceExplorerItemViewModel;
}) {
  const className = cn(
    "mt-0.5 size-5 shrink-0",
    relationTextColor(item.relation),
  );
  if (item.relation === "supports") {
    return <CheckCircle2Icon className={className} aria-hidden="true" />;
  }
  if (item.relation === "contradicts") {
    return <XCircleIcon className={className} aria-hidden="true" />;
  }
  return <HelpCircleIcon className={className} aria-hidden="true" />;
}

function EvidenceChip({
  relation,
  children,
}: {
  relation?: CommerceEvidenceExplorerItemViewModel["relation"];
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "rounded-md border px-2 py-1 text-[10px] font-medium",
        !relation && "border-black/[0.08] bg-[#fafaf8] text-[#6f6f69]",
        relation === "supports" &&
          "border-[#cfe1d1] bg-[#f5faf5] text-[#3d6a43]",
        relation === "contradicts" && "border-red-200 bg-red-50 text-red-700",
        relation === "unknown" &&
          "border-black/[0.08] bg-[#f3f3f0] text-[#707069]",
      )}
    >
      {children}
    </span>
  );
}

function EvidenceEmptyState() {
  return (
    <div className="mt-8 flex min-h-[32vh] flex-col items-center justify-center rounded-2xl border border-dashed border-black/[0.12] px-6 text-center">
      <FileTextIcon className="size-6 text-[#777771]" aria-hidden="true" />
      <h3 className="mt-4 text-base font-semibold text-[#353530]">
        还没有可展示的证据
      </h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#777771]">
        证据必须先完成持久化和案例归属校验，才会显示在这里。
      </p>
    </div>
  );
}

function relationActiveBorder(
  relation: CommerceEvidenceExplorerItemViewModel["relation"],
) {
  if (relation === "supports")
    return "border-[#bcd9c0] shadow-[inset_3px_0_0_#4f8b59]";
  if (relation === "contradicts")
    return "border-red-200 shadow-[inset_3px_0_0_#dc2626]";
  return "border-black/[0.14] shadow-[inset_3px_0_0_#8a8a84]";
}

function relationTextColor(
  relation: CommerceEvidenceExplorerItemViewModel["relation"],
) {
  if (relation === "supports") return "text-[#3f7d49]";
  if (relation === "contradicts") return "text-red-600";
  return "text-[#777771]";
}
