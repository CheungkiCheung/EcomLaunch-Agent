import { Gamepad2Icon, LoaderCircleIcon } from "lucide-react";
import Link from "next/link";

import type { CommerceRunTaskActivityViewModel } from "@/core/commerce/run-task-activity-view-model";
import { cn } from "@/lib/utils";

export function CommerceRunActivityStrip({
  viewModel,
  isLoading,
  isRefreshing,
  error,
  collaborationHref,
}: {
  viewModel: CommerceRunTaskActivityViewModel;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  collaborationHref: string;
}) {
  if (viewModel.items.length === 0 && !isLoading && !error) return null;

  return (
    <div
      className="border-border/70 bg-background/92 mb-2 flex w-full items-start gap-2 rounded-xl border px-3 py-2 shadow-xs backdrop-blur"
      data-commerce-run-activity
    >
      <details className="group min-w-0 flex-1">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-xs [&::-webkit-details-marker]:hidden">
          <span
            className={cn(
              "size-2 shrink-0 rounded-full",
              summaryDotClass(viewModel),
            )}
            aria-hidden="true"
          />
          <span className="font-medium">
            {viewModel.summary.total > 0
              ? `${viewModel.summary.total} 个协作任务`
              : "正在准备协作任务"}
          </span>
          {viewModel.summary.active > 0 && (
            <span className="text-muted-foreground">
              {viewModel.summary.active} 个进行中
            </span>
          )}
          {viewModel.summary.waiting > 0 && (
            <span className="text-amber-700 dark:text-amber-300">
              {viewModel.summary.waiting} 个等待中
            </span>
          )}
          {isRefreshing && (
            <LoaderCircleIcon
              className="text-muted-foreground size-3 animate-spin motion-reduce:animate-none"
              aria-label="正在同步任务状态"
            />
          )}
          {isLoading && viewModel.items.length === 0 && (
            <span className="text-muted-foreground">正在读取真实任务事件</span>
          )}
          {error && <span className="text-destructive">协作状态暂不可用</span>}
          <span className="text-muted-foreground ml-auto group-open:hidden">
            展开过程
          </span>
          <span className="text-muted-foreground ml-auto hidden group-open:inline">
            收起过程
          </span>
        </summary>

        {viewModel.items.length > 0 && (
          <div className="mt-2 grid gap-1.5 border-t pt-2 sm:grid-cols-3">
            {viewModel.items.map((item) => (
              <div
                key={item.taskId}
                className="bg-muted/35 min-w-0 rounded-lg px-2.5 py-2"
                data-commerce-task-id={item.taskId}
                data-commerce-task-status={item.status}
              >
                <div className="flex items-center gap-1.5 text-xs">
                  <span
                    className={cn(
                      "size-1.5 shrink-0 rounded-full",
                      taskStatusDotClass(item.status),
                    )}
                    aria-hidden="true"
                  />
                  <span className="font-medium">{item.profileLabel}</span>
                  <span className="text-muted-foreground ml-auto">
                    {item.statusLabel}
                  </span>
                </div>
                <p className="text-muted-foreground mt-1 truncate text-[11px]">
                  {item.detailLabel}
                </p>
              </div>
            ))}
          </div>
        )}

        {(viewModel.hasIncompleteEventPages ||
          viewModel.wasReordered ||
          viewModel.unknownEventCount > 0) && (
          <p className="text-muted-foreground mt-2 text-[11px]">
            当前投影包含未完成分页、乱序恢复或未知事件，请在协作空间查看审计提示。
          </p>
        )}
      </details>

      <Link
        className="text-primary hover:bg-primary/8 inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors"
        href={collaborationHref}
      >
        <Gamepad2Icon className="size-3.5" />
        查看协作空间
      </Link>
    </div>
  );
}

function summaryDotClass(viewModel: CommerceRunTaskActivityViewModel) {
  if (viewModel.summary.active > 0) return "bg-sky-500";
  if (viewModel.summary.waiting > 0) return "bg-amber-500";
  if (viewModel.summary.blocked > 0) return "bg-orange-600";
  if (
    viewModel.summary.failed > 0 ||
    viewModel.summary.cancelled > 0 ||
    viewModel.summary.timedOut > 0
  ) {
    return "bg-rose-500";
  }
  if (
    viewModel.summary.total > 0 &&
    viewModel.summary.completed === viewModel.summary.total
  ) {
    return "bg-emerald-500";
  }
  return "bg-muted-foreground";
}

function taskStatusDotClass(
  status: CommerceRunTaskActivityViewModel["items"][number]["status"],
) {
  return {
    queued: "bg-slate-400",
    working: "bg-sky-500",
    waiting: "bg-amber-500",
    approval: "bg-amber-600",
    blocked: "bg-orange-600",
    completed: "bg-emerald-500",
    failed: "bg-rose-500",
    cancelled: "bg-slate-500",
    timed_out: "bg-violet-500",
  }[status];
}
