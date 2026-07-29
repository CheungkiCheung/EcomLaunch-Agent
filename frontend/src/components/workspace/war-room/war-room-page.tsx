"use client";

import type { Run } from "@langchain/langgraph-sdk";
import {
  ActivityIcon,
  CheckCircle2Icon,
  ExternalLinkIcon,
  FileStackIcon,
  RefreshCwIcon,
  ShieldAlertIcon,
  SparklesIcon,
  UsersIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useThreadRuns, useThreads } from "@/core/threads/hooks";
import type { AgentThread } from "@/core/threads/types";
import { agentNameOfThread } from "@/core/threads/utils";
import { cn } from "@/lib/utils";

import { buildWarRoomSnapshot } from "./adapter";
import { WAR_ROOM_POLL_INTERVAL_MS } from "./config";
import type {
  WarRoomActorId,
  WarRoomActorSnapshot,
  WarRoomRunStatus,
  WarRoomStatus,
} from "./types";
import { WarRoomCanvas } from "./war-room-canvas";

const STATUS_LABELS: Record<WarRoomStatus, string> = {
  idle: "待命",
  queued: "排队中",
  working: "执行中",
  done: "已完成",
  failed: "遇到阻塞",
};

function latestThread(threads: AgentThread[], agentName: string) {
  return threads.find((thread) => agentNameOfThread(thread) === agentName);
}

function latestRunStatus(
  runs: Run[] | undefined,
): WarRoomRunStatus | undefined {
  if (!runs?.length) return undefined;
  return [...runs].sort((left, right) => {
    const leftDate = new Date(left.created_at ?? 0).getTime();
    const rightDate = new Date(right.created_at ?? 0).getTime();
    return rightDate - leftDate;
  })[0]?.status as WarRoomRunStatus | undefined;
}

function actorStatusClass(status: WarRoomStatus) {
  if (status === "working")
    return "border-orange-300 bg-orange-50 text-orange-700";
  if (status === "queued") return "border-amber-300 bg-amber-50 text-amber-700";
  if (status === "done")
    return "border-emerald-300 bg-emerald-50 text-emerald-700";
  if (status === "failed") return "border-red-300 bg-red-50 text-red-700";
  return "border-stone-200 bg-white/85 text-stone-500";
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/80 bg-white/82 px-3 py-2 shadow-sm backdrop-blur-md">
      <Icon className="size-4 text-orange-500" />
      <div>
        <div className="text-[10px] font-medium tracking-wide text-stone-400 uppercase">
          {label}
        </div>
        <div className="text-sm font-semibold text-stone-700">{value}</div>
      </div>
    </div>
  );
}

function ActorCard({
  actor,
  selected,
  onSelect,
}: {
  actor: WarRoomActorSnapshot;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex min-w-0 items-center gap-2 rounded-xl border bg-white/88 px-2.5 py-2 text-left shadow-sm backdrop-blur-md transition hover:-translate-y-0.5 hover:shadow-md",
        selected
          ? "border-orange-300 ring-2 ring-orange-200/70"
          : "border-white/90",
      )}
    >
      <div className="size-9 shrink-0 overflow-hidden rounded-lg bg-gradient-to-b from-orange-50 to-stone-100">
        <img
          src={`/war-room/agent-${actor.id}.png`}
          alt=""
          className="h-[76px] w-full translate-y-0 object-contain object-top"
        />
      </div>
      <div className="min-w-0">
        <div className="truncate text-xs font-semibold text-stone-700">
          {actor.name}
        </div>
        <div className="mt-0.5 flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block size-1.5 rounded-full",
              actor.status === "working"
                ? "animate-pulse bg-orange-500"
                : actor.status === "done"
                  ? "bg-emerald-500"
                  : actor.status === "failed"
                    ? "bg-red-500"
                    : "bg-stone-300",
            )}
          />
          <span className="truncate text-[10px] text-stone-500">
            {STATUS_LABELS[actor.status]}
          </span>
        </div>
      </div>
    </button>
  );
}

export function WarRoomPage() {
  const threadsQuery = useThreads();
  const threads = threadsQuery.data ?? [];
  const ecomThread = latestThread(threads, "ecom-launch");
  const dataThread = latestThread(threads, "data-inspector");
  const ecomRuns = useThreadRuns(ecomThread?.thread_id);
  const dataRuns = useThreadRuns(dataThread?.thread_id);
  const [selectedActorId, setSelectedActorId] =
    useState<WarRoomActorId>("ecom-launch");

  const refresh = useCallback(() => {
    void threadsQuery.refetch();
    void ecomRuns.refetch();
    void dataRuns.refetch();
  }, [dataRuns, ecomRuns, threadsQuery]);

  useEffect(() => {
    const timer = window.setInterval(refresh, WAR_ROOM_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const snapshot = useMemo(
    () =>
      buildWarRoomSnapshot({
        ecomThread,
        ecomRunStatus: latestRunStatus(ecomRuns.data),
        dataThread,
        dataRunStatus: latestRunStatus(dataRuns.data),
      }),
    [dataRuns.data, dataThread, ecomRuns.data, ecomThread],
  );
  const selectedActor =
    snapshot.actors.find((actor) => actor.id === selectedActorId) ??
    snapshot.actors[0]!;

  return (
    <div className="relative flex h-full min-h-0 flex-col overflow-hidden bg-[#f8f4ec]">
      <header className="z-30 flex h-14 shrink-0 items-center gap-3 border-b border-orange-100/80 bg-white/86 px-4 backdrop-blur-xl">
        <SidebarTrigger className="-ml-2 md:hidden" />
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 to-rose-400 text-white shadow-sm">
          <SparklesIcon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold text-stone-800">
            智能商业作战室
          </h1>
          <p className="truncate text-[11px] text-stone-500">
            EcomLaunch 团队与 Growth Analyst 的真实运行现场
          </p>
        </div>
        <Badge
          variant="outline"
          className="hidden border-orange-200 bg-orange-50 text-orange-700 sm:inline-flex"
        >
          {snapshot.activeCount > 0
            ? `${snapshot.activeCount} 位正在执行`
            : "全员待命"}
        </Badge>
        <Button size="sm" variant="outline" onClick={refresh}>
          <RefreshCwIcon
            className={cn(
              "size-3.5",
              threadsQuery.isFetching && "animate-spin",
            )}
          />
          <span className="hidden sm:inline">刷新</span>
        </Button>
      </header>

      <main className="relative min-h-0 flex-1 p-2 sm:p-3">
        <div className="relative size-full overflow-hidden rounded-2xl border border-white bg-white shadow-[0_18px_60px_rgba(161,116,74,0.14)]">
          <WarRoomCanvas
            snapshot={snapshot}
            onActorSelect={setSelectedActorId}
          />

          <div className="pointer-events-none absolute top-3 left-3 z-20 flex max-w-[calc(100%-1.5rem)] gap-2 overflow-x-auto sm:top-4 sm:left-4">
            <Metric
              icon={ActivityIcon}
              label="执行中"
              value={snapshot.activeCount}
            />
            <Metric
              icon={CheckCircle2Icon}
              label="已完成"
              value={snapshot.completedCount}
            />
            <Metric
              icon={FileStackIcon}
              label="产物"
              value={snapshot.artifactCount}
            />
            {snapshot.failedCount > 0 && (
              <Metric
                icon={ShieldAlertIcon}
                label="阻塞"
                value={snapshot.failedCount}
              />
            )}
          </div>

          <section className="absolute right-3 bottom-3 left-3 z-30 sm:right-4 sm:bottom-4 sm:left-4">
            <div className="mb-2 hidden grid-cols-6 gap-2 xl:grid">
              {snapshot.actors.map((actor) => (
                <ActorCard
                  key={actor.id}
                  actor={actor}
                  selected={actor.id === selectedActor.id}
                  onSelect={() => setSelectedActorId(actor.id)}
                />
              ))}
            </div>

            <div className="flex items-center gap-3 rounded-2xl border border-white/90 bg-white/90 p-3 shadow-lg backdrop-blur-xl sm:p-4">
              <div
                className="hidden size-14 shrink-0 overflow-hidden rounded-xl sm:block"
                style={{ backgroundColor: `${selectedActor.accent}18` }}
              >
                <img
                  src={`/war-room/agent-${selectedActor.id}.png`}
                  alt=""
                  className="h-28 w-full object-contain object-top"
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-sm font-semibold text-stone-800">
                    {selectedActor.name}
                  </h2>
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[10px] font-medium",
                      actorStatusClass(selectedActor.status),
                    )}
                  >
                    {STATUS_LABELS[selectedActor.status]}
                  </span>
                  <span className="hidden text-[10px] text-stone-400 md:inline">
                    {selectedActor.role}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-stone-600">
                  {selectedActor.summary}
                </p>
                {(selectedActor.tool ?? selectedActor.task) && (
                  <div className="mt-1.5 flex min-w-0 items-center gap-2 text-[10px] text-stone-500">
                    {selectedActor.tool && (
                      <span className="shrink-0 rounded bg-stone-100 px-1.5 py-0.5 font-mono">
                        {selectedActor.tool}
                      </span>
                    )}
                    {selectedActor.task && (
                      <span className="truncate">{selectedActor.task}</span>
                    )}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="hidden items-center gap-1 text-[10px] text-stone-400 lg:flex">
                  <UsersIcon className="size-3.5" />
                  点击场景人物切换
                </div>
                {selectedActor.href ? (
                  <Button size="sm" asChild>
                    <Link href={selectedActor.href}>
                      进入对话
                      <ExternalLinkIcon className="size-3.5" />
                    </Link>
                  </Button>
                ) : (
                  <Button size="sm" asChild>
                    <Link
                      href={`/workspace/agents/${selectedActor.team}/chats/new`}
                    >
                      创建任务
                      <ExternalLinkIcon className="size-3.5" />
                    </Link>
                  </Button>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
