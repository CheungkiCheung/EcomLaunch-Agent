import {
  ArrowRightIcon,
  CheckCircle2Icon,
  CircleAlertIcon,
  CircleDashedIcon,
  Clock3Icon,
} from "lucide-react";

import type {
  CommerceWarRoomLaneStatus,
  CommerceWarRoomViewModel,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

export function CommerceWarRoomView({
  viewModel,
  isLoading,
  error,
  onSelectRun,
  onOpenCase,
  onOpenRun,
}: {
  viewModel: CommerceWarRoomViewModel;
  isLoading: boolean;
  error: string | null;
  onSelectRun: (runId: string) => void;
  onOpenCase: (caseId: string) => void;
  onOpenRun: (runId: string) => void;
}) {
  const selected = viewModel.selected;
  return (
    <section
      className="mx-auto w-full max-w-[1280px] px-5 py-7 sm:px-8 lg:px-9"
      data-testid="commerce-war-room"
    >
      <header>
        <p className="text-xs font-medium tracking-[0.12em] text-[#85857f] uppercase">
          作战室
        </p>
        <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.03em] text-[#292925]">
          {viewModel.title}
        </h1>
        <p className="mt-2 max-w-[760px] text-sm leading-6 text-[#6f6f69]">
          {viewModel.subtitle}
        </p>
      </header>

      {error && (
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          {error}
        </div>
      )}

      {isLoading && viewModel.items.length === 0 ? (
        <div className="mt-8 flex min-h-64 items-center justify-center text-sm text-[#73736d]">
          正在读取持久化运行事件
        </div>
      ) : viewModel.items.length === 0 || !selected ? (
        <div className="mt-8 rounded-2xl border border-dashed border-black/10 bg-white px-6 py-12 text-center">
          <p className="font-medium text-[#343430]">尚无可观察的调查运行</p>
          <p className="mt-2 text-sm text-[#777771]">
            创建运行并持久化事件后，这里才会显示调查状态。
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <nav
            className="rounded-2xl border border-black/[0.08] bg-white p-2"
            aria-label="运行列表"
          >
            {viewModel.items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={cn(
                  "w-full rounded-xl px-3 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2",
                  item.id === selected.id
                    ? "bg-[#f1f1ed]"
                    : "hover:bg-black/[0.03]",
                )}
                onClick={() => onSelectRun(item.id)}
              >
                <span className="block truncate text-sm font-medium text-[#32322f]">
                  {item.title}
                </span>
                <span className="mt-1 block truncate text-xs text-[#7a7a74]">
                  {item.caseTitle} · {item.statusLabel} · {item.updatedLabel}
                </span>
              </button>
            ))}
          </nav>

          <article className="min-w-0 overflow-hidden rounded-2xl border border-black/[0.08] bg-white">
            <div className="border-b border-black/[0.07] px-5 py-5 sm:px-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs text-[#777771]">{selected.caseTitle}</p>
                  <h2 className="mt-1 text-xl font-semibold tracking-[-0.02em] text-[#2b2b28]">
                    {selected.title}
                  </h2>
                  <p className="mt-2 text-xs text-[#7a7a74]">
                    {selected.statusLabel} · {selected.shortId} ·{" "}
                    {selected.latestEventLabel}
                  </p>
                </div>
                <p className="inline-flex items-center gap-2 rounded-full bg-[#f3f3ef] px-3 py-1.5 text-xs text-[#666660]">
                  <Clock3Icon className="size-3.5" aria-hidden="true" />
                  {selected.quietLabel}
                </p>
              </div>

              <dl className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-4">
                {selected.summary.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-xl border border-black/[0.06] bg-[#fafaf8] px-3 py-3"
                  >
                    <dt className="text-xs text-[#83837d]">{item.label}</dt>
                    <dd className="mt-1 text-sm font-medium text-[#343430]">
                      {item.valueLabel}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="grid min-[1480px]:grid-cols-[minmax(0,1fr)_330px]">
              <div className="px-5 py-6 sm:px-6">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium tracking-[0.1em] text-[#85857f] uppercase">
                      并行路径
                    </p>
                    <h3 className="mt-1 font-semibold text-[#30302d]">
                      调查泳道
                    </h3>
                  </div>
                  {selected.wasReordered && (
                    <span className="text-xs text-amber-700">
                      事件已按序重排
                    </span>
                  )}
                </div>

                <div className="mt-4 space-y-2">
                  {selected.lanes.map((lane) => (
                    <div
                      key={lane.key}
                      className="grid gap-3 rounded-xl border border-black/[0.07] px-4 py-3 sm:grid-cols-[150px_minmax(0,1fr)_110px] sm:items-center"
                    >
                      <div className="flex items-center gap-2">
                        <LaneIcon status={lane.status} />
                        <span className="text-sm font-medium text-[#343430]">
                          {lane.title}
                        </span>
                      </div>
                      <div>
                        <p className="text-sm text-[#575752]">
                          {lane.description}
                        </p>
                        <p className="mt-0.5 text-xs text-[#8a8a84]">
                          {lane.eventLabel}
                        </p>
                      </div>
                      <span className={laneStatusClass(lane.status)}>
                        {lane.statusLabel}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-6 grid gap-3 lg:grid-cols-2">
                  <section className="rounded-xl border border-black/[0.07] p-4">
                    <h3 className="text-sm font-semibold text-[#343430]">
                      当前证据构成
                    </h3>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      {selected.evidenceSummary.map((item) => (
                        <div
                          key={item.label}
                          className={cn(
                            "rounded-lg px-3 py-3",
                            item.tone === "support" && "bg-emerald-50",
                            item.tone === "contradict" && "bg-rose-50",
                            item.tone === "unknown" && "bg-stone-100",
                          )}
                        >
                          <p className="text-xs text-[#73736d]">{item.label}</p>
                          <p className="mt-1 text-lg font-semibold text-[#33332f]">
                            {item.countLabel}
                          </p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-xs leading-5 text-[#7b7b75]">
                      {selected.evidenceBoundaryLabel}
                    </p>
                  </section>

                  <section className="rounded-xl border border-black/[0.07] p-4">
                    <h3 className="text-sm font-semibold text-[#343430]">
                      最新检查点
                    </h3>
                    <p className="mt-3 text-sm leading-6 text-[#5f5f59]">
                      {selected.checkpointLabel}
                    </p>
                  </section>
                </div>
              </div>

              <aside className="border-t border-black/[0.07] bg-[#fafaf8] px-5 py-6 min-[1480px]:border-t-0 min-[1480px]:border-l sm:px-6">
                <p className="text-xs font-medium tracking-[0.1em] text-[#85857f] uppercase">
                  领域事件流
                </p>
                <h3 className="mt-1 font-semibold text-[#30302d]">
                  按运行事件序号排序
                </h3>
                <ol className="mt-4 space-y-3">
                  {selected.eventItems.map((item) => (
                    <li key={item.id} className="flex gap-3">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-black/[0.08] bg-white text-[11px] text-[#777771]">
                        {item.sequenceLabel}
                      </span>
                      <div className="min-w-0 pt-0.5">
                        <p
                          className={cn(
                            "text-sm text-[#4f4f4a]",
                            item.kind === "unknown" && "text-amber-800",
                          )}
                        >
                          {item.title}
                        </p>
                        <p className="mt-0.5 text-xs text-[#91918b]">
                          {item.timeLabel}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              </aside>
            </div>

            <footer className="flex flex-col gap-2 border-t border-black/[0.07] px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
              <button
                type="button"
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-black/[0.09] px-3 text-sm text-[#4f4f4a] hover:bg-black/[0.03]"
                onClick={() => onOpenCase(selected.caseId)}
              >
                打开案例
                <ArrowRightIcon className="size-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-[#292925] px-3 text-sm text-white hover:bg-[#171715]"
                onClick={() => onOpenRun(selected.id)}
              >
                检查完整运行记录
                <ArrowRightIcon className="size-4" aria-hidden="true" />
              </button>
            </footer>
          </article>
        </div>
      )}
    </section>
  );
}

function LaneIcon({ status }: { status: CommerceWarRoomLaneStatus }) {
  if (status === "completed") {
    return (
      <CheckCircle2Icon
        className="size-4 text-emerald-700"
        aria-hidden="true"
      />
    );
  }
  if (status === "blocked") {
    return (
      <CircleAlertIcon className="size-4 text-rose-700" aria-hidden="true" />
    );
  }
  return (
    <CircleDashedIcon className="size-4 text-[#777771]" aria-hidden="true" />
  );
}

function laneStatusClass(status: CommerceWarRoomLaneStatus) {
  return cn(
    "w-fit rounded-full px-2.5 py-1 text-xs font-medium sm:justify-self-end",
    status === "completed" && "bg-emerald-50 text-emerald-800",
    status === "running" && "bg-sky-50 text-sky-800",
    status === "waiting" && "bg-amber-50 text-amber-800",
    status === "blocked" && "bg-rose-50 text-rose-800",
    status === "not_started" && "bg-stone-100 text-stone-600",
  );
}
