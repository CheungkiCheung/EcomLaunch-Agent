"use client";

import type { Run } from "@langchain/langgraph-sdk";
import {
  ActivityIcon,
  CheckCircle2Icon,
  FileStackIcon,
  Globe2Icon,
  Maximize2Icon,
  Minimize2Icon,
  RefreshCwIcon,
  ShieldAlertIcon,
  SparklesIcon,
  UsersIcon,
  XIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import {
  useThreadRuns,
  useThreads,
  useThreadState,
} from "@/core/threads/hooks";
import type { AgentThread } from "@/core/threads/types";
import { agentNameOfThread } from "@/core/threads/utils";
import { cn } from "@/lib/utils";

import { ActorChatPanel } from "./actor-chat-panel";
import { buildWarRoomSnapshot, hydrateWarRoomThread } from "./adapter";
import { WAR_ROOM_POLL_INTERVAL_MS } from "./config";
import type { ActorView } from "./office-scene";
import type {
  WarRoomActorId,
  WarRoomActorSnapshot,
  WarRoomRunStatus,
  WarRoomSource,
  WarRoomStatus,
} from "./types";
import { WarRoomCanvas } from "./war-room-canvas";

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
  testId,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  testId?: string;
}) {
  return (
    <div
      className="flex items-center gap-2 rounded-xl border border-white/80 bg-white/82 px-3 py-2 shadow-sm backdrop-blur-md"
      data-testid={testId}
    >
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

function ActorSpritePortrait({
  actorId,
  large = false,
}: {
  actorId: WarRoomActorId;
  large?: boolean;
}) {
  const frameWidth = large ? 40 : 32;
  const frameHeight = large ? 60 : 48;

  return (
    <span
      aria-hidden="true"
      className="block shrink-0 bg-left-top bg-no-repeat"
      style={{
        width: frameWidth,
        height: frameHeight,
        backgroundImage: `url(/war-room-original/characters/${actorId}.png)`,
        backgroundSize: `${frameWidth * 4}px ${frameHeight}px`,
        imageRendering: "pixelated",
      }}
    />
  );
}

function ActorCard({
  actor,
  selected,
  onSelect,
  statusLabels,
}: {
  actor: WarRoomActorSnapshot;
  selected: boolean;
  onSelect: () => void;
  statusLabels: Record<WarRoomStatus, string>;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex h-[60px] min-w-0 items-center gap-2 rounded-xl border bg-white/88 px-2.5 text-left shadow-sm backdrop-blur-md transition hover:-translate-y-0.5 hover:shadow-md",
        selected
          ? "border-orange-300 ring-2 ring-orange-200/70"
          : "border-white/90",
      )}
    >
      <div className="flex h-12 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gradient-to-b from-orange-50 to-stone-100">
        <ActorSpritePortrait actorId={actor.id} />
      </div>
      <div className="min-w-0">
        <div className="truncate text-[11px] font-semibold text-stone-700">
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
            {statusLabels[actor.status]}
          </span>
        </div>
      </div>
    </button>
  );
}

export function WarRoomPage() {
  const { locale, t, changeLocale } = useI18n();
  const copy = t.warRoom;
  const threadsQuery = useThreads();
  const threads = threadsQuery.data ?? [];
  const ecomThread = latestThread(threads, "ecom-launch");
  const dataThread = latestThread(threads, "data-inspector");
  const ecomRuns = useThreadRuns(ecomThread?.thread_id);
  const dataRuns = useThreadRuns(dataThread?.thread_id);
  const ecomState = useThreadState(ecomThread?.thread_id);
  const dataState = useThreadState(dataThread?.thread_id);
  const hydratedEcomThread = useMemo(
    () => hydrateWarRoomThread(ecomThread, ecomState.data),
    [ecomState.data, ecomThread],
  );
  const hydratedDataThread = useMemo(
    () => hydrateWarRoomThread(dataThread, dataState.data),
    [dataState.data, dataThread],
  );
  const [selectedActorId, setSelectedActorId] =
    useState<WarRoomActorId>("ecom-launch");
  const [selectedView, setSelectedView] = useState<ActorView>("chat");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMinimized, setChatMinimized] = useState(false);

  const handleActorSelect = useCallback(
    (actorId: WarRoomActorId, view: ActorView = "chat") => {
      setSelectedActorId(actorId);
      setSelectedView(view);
      setChatOpen(true);
      setChatMinimized(false);
    },
    [],
  );

  const selectActor = useCallback((actorId: WarRoomActorId) => {
    setSelectedActorId(actorId);
    setSelectedView("chat");
  }, []);

  const openSelectedActorView = useCallback((view: ActorView) => {
    setSelectedView(view);
    setChatOpen(true);
    setChatMinimized(false);
  }, []);

  const closeChat = useCallback(() => {
    setChatOpen(false);
    setChatMinimized(false);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeChat();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeChat]);

  const refresh = useCallback(() => {
    void threadsQuery.refetch();
    void ecomRuns.refetch();
    void dataRuns.refetch();
    void ecomState.refetch();
    void dataState.refetch();
  }, [dataRuns, dataState, ecomRuns, ecomState, threadsQuery]);

  useEffect(() => {
    const timer = window.setInterval(refresh, WAR_ROOM_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const snapshot = useMemo(
    () =>
      buildWarRoomSnapshot(
        {
          ecomThread: hydratedEcomThread,
          ecomRunStatus: latestRunStatus(ecomRuns.data),
          ecomRuns: ecomRuns.data as WarRoomSource["ecomRuns"],
          dataThread: hydratedDataThread,
          dataRunStatus: latestRunStatus(dataRuns.data),
        },
        copy,
      ),
    [
      copy,
      dataRuns.data,
      ecomRuns.data,
      hydratedDataThread,
      hydratedEcomThread,
    ],
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
            {copy.title}
          </h1>
          <p className="truncate text-[11px] text-stone-500">{copy.subtitle}</p>
        </div>
        <Badge
          variant="outline"
          className="hidden border-orange-200 bg-orange-50 text-orange-700 sm:inline-flex"
        >
          <span
            className={cn(
              "mr-1 inline-block size-1.5 rounded-full",
              snapshot.runStatus === "running"
                ? "animate-pulse bg-orange-500"
                : snapshot.runStatus === "success"
                  ? "bg-emerald-500"
                  : snapshot.runStatus === "error"
                    ? "bg-red-500"
                    : "bg-stone-400",
            )}
          />
          {snapshot.activeCount > 0
            ? copy.activeAgents(snapshot.activeCount)
            : copy.allIdle}
        </Badge>
        <Button
          size="sm"
          variant="ghost"
          className="px-2 text-xs text-stone-600"
          onClick={() => changeLocale(locale === "en-US" ? "zh-CN" : "en-US")}
          aria-label={copy.switchLanguage}
          title={copy.switchLanguage}
        >
          <Globe2Icon className="size-3.5" />
          <span>{locale === "en-US" ? "中文" : "EN"}</span>
        </Button>
        <Button size="sm" variant="outline" onClick={refresh}>
          <RefreshCwIcon
            className={cn(
              "size-3.5",
              threadsQuery.isFetching && "animate-spin",
            )}
          />
          <span className="hidden sm:inline">{copy.refresh}</span>
        </Button>
      </header>

      <main className="relative min-h-0 flex-1 gap-3 overflow-y-auto p-2 sm:p-3 xl:grid xl:grid-cols-[minmax(0,1fr)_21rem] xl:overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div
          data-testid="war-room-scene"
          className="relative h-[clamp(500px,68vh,760px)] min-w-0 overflow-hidden rounded-2xl border border-white bg-white shadow-[0_18px_60px_rgba(161,116,74,0.14)] xl:h-full xl:min-h-0"
        >
          <WarRoomCanvas
            snapshot={snapshot}
            onActorSelect={handleActorSelect}
            labels={copy}
          />

          {/* Floating pixel-style chat card over the scene */}
          {chatOpen && (
            <div
              className={cn(
                "absolute right-3 z-40 flex flex-col overflow-hidden rounded-xl border border-[#4a4238] bg-[#252219] shadow-[4px_4px_16px_rgba(0,0,0,0.5)] transition-all duration-200 sm:right-4",
                chatMinimized
                  ? "top-3 w-[240px] sm:top-4"
                  : "top-3 bottom-3 w-[min(420px,calc(100%-1.5rem))] sm:top-4 sm:bottom-4",
              )}
            >
              <div className="flex shrink-0 items-center gap-2 px-3 py-2.5">
                <div
                  className="flex h-10 w-9 shrink-0 items-start justify-center overflow-hidden rounded-lg"
                  style={{ backgroundColor: `${selectedActor.accent}26` }}
                >
                  <ActorSpritePortrait actorId={selectedActor.id} />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-xs font-semibold text-[#e8e2d8]">
                    {selectedActor.name}
                  </h3>
                  <p className="truncate text-[10px] text-[#a09888]">
                    {selectedActor.role}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setChatMinimized((v) => !v)}
                  className="flex size-7 items-center justify-center rounded-md text-[#a09888] transition hover:bg-[#4a4238]/60 hover:text-[#f5e6b3]"
                  aria-label={
                    chatMinimized ? copy.expandChat : copy.minimizeChat
                  }
                  title={chatMinimized ? copy.expand : copy.minimize}
                >
                  {chatMinimized ? (
                    <Maximize2Icon className="size-4" />
                  ) : (
                    <Minimize2Icon className="size-4" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={closeChat}
                  className="flex size-7 items-center justify-center rounded-md text-[#a09888] transition hover:bg-[#4a4238]/60 hover:text-[#f5e6b3]"
                  aria-label={copy.closeChat}
                  title={copy.close}
                >
                  <XIcon className="size-4" />
                </button>
              </div>
              <div
                className={cn(
                  "mx-1 mb-1 min-h-0 flex-1 overflow-hidden rounded-lg bg-[#f5f1e8]",
                  chatMinimized && "hidden",
                )}
              >
                <ActorChatPanel
                  actor={selectedActor}
                  initialView={selectedView}
                />
              </div>
            </div>
          )}

          <div className="pointer-events-none absolute top-3 left-3 z-20 flex max-w-[calc(100%-1.5rem)] gap-2 overflow-x-auto sm:top-4 sm:left-4">
            <Metric
              icon={ActivityIcon}
              label={copy.running}
              value={snapshot.activeCount}
            />
            <Metric
              icon={CheckCircle2Icon}
              label={copy.completed}
              value={snapshot.completedCount}
            />
            <Metric
              icon={FileStackIcon}
              label={copy.artifacts}
              value={snapshot.artifactCount}
              testId="war-room-artifact-count"
            />
            {snapshot.failedCount > 0 && (
              <Metric
                icon={ShieldAlertIcon}
                label={copy.blocked}
                value={snapshot.failedCount}
              />
            )}
          </div>
        </div>

        <aside
          data-testid="war-room-agent-sidebar"
          className="flex min-h-0 w-full shrink-0 flex-col gap-3 xl:overflow-y-auto"
        >
          <section className="rounded-2xl border border-white/90 bg-white/86 p-3 shadow-sm backdrop-blur-xl">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UsersIcon className="size-4 text-orange-500" />
                <h2 className="text-xs font-semibold text-stone-700">
                  {copy.teamStatus}
                </h2>
              </div>
              <span className="text-[10px] text-stone-400">
                {copy.switchActor}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {snapshot.actors.map((actor) => (
                <ActorCard
                  key={actor.id}
                  actor={actor}
                  selected={actor.id === selectedActor.id}
                  onSelect={() => selectActor(actor.id)}
                  statusLabels={copy.statuses}
                />
              ))}
            </div>
          </section>

          <section
            data-testid="war-room-selected-actor"
            className="rounded-2xl border border-white/90 bg-white/90 p-3 shadow-sm backdrop-blur-xl"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div
                className="flex h-[66px] w-12 shrink-0 items-start justify-center overflow-hidden rounded-xl"
                style={{ backgroundColor: `${selectedActor.accent}18` }}
              >
                <ActorSpritePortrait actorId={selectedActor.id} large />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 items-center gap-2">
                  <h2 className="truncate text-sm font-semibold text-stone-800">
                    {selectedActor.name}
                  </h2>
                  <span
                    className={cn(
                      "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium",
                      actorStatusClass(selectedActor.status),
                    )}
                  >
                    {copy.statuses[selectedActor.status]}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-[10px] text-stone-400">
                  {selectedActor.role}
                </p>
                <p className="mt-1.5 line-clamp-2 text-[11px] leading-4 text-stone-600">
                  {selectedActor.summary}
                </p>
              </div>
            </div>

            {(selectedActor.tool ?? selectedActor.task) && (
              <div className="mt-2 flex min-w-0 items-center gap-2 rounded-lg bg-stone-50/90 px-2 py-1.5 text-[10px] text-stone-500">
                {selectedActor.tool && (
                  <span className="shrink-0 rounded bg-white px-1.5 py-0.5 font-mono shadow-sm">
                    {selectedActor.tool}
                  </span>
                )}
                {selectedActor.task && (
                  <span className="truncate">{selectedActor.task}</span>
                )}
              </div>
            )}

            <div className="mt-3 grid grid-cols-3 gap-2">
              <Button
                size="sm"
                className="h-8 bg-orange-500 text-[11px] hover:bg-orange-600"
                onClick={() => openSelectedActorView("chat")}
              >
                {copy.chat}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-[11px]"
                disabled={!selectedActor.task}
                onClick={() => openSelectedActorView("task")}
              >
                {copy.task}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-[11px]"
                disabled={
                  !selectedActor.taskDetail?.output &&
                  selectedActor.artifacts.length === 0
                }
                onClick={() => openSelectedActorView("output")}
              >
                {copy.output}
              </Button>
            </div>
          </section>

          <details className="group rounded-xl border border-white/90 bg-white/85 shadow-sm">
            <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-[10px] font-medium tracking-wide text-stone-400 uppercase select-none">
              {copy.runDetails}
              <span className="transition-transform group-open:rotate-180">
                ▾
              </span>
            </summary>
            <div className="space-y-3 px-3 pb-3">
              <StagePanel
                stages={snapshot.stages}
                runStatus={snapshot.runStatus}
                copy={copy}
              />
              <MetricsPanel metrics={snapshot.metrics} copy={copy} />
              <TaskQueuePanel actors={snapshot.actors} copy={copy} />
              <ArtifactsPanel
                artifacts={
                  new Set(snapshot.actors.flatMap((actor) => actor.artifacts))
                }
                copy={copy}
              />
              {snapshot.runTitle && (
                <div className="rounded-xl border border-white/90 bg-stone-50/80 px-3 py-2">
                  <p className="text-[10px] font-medium tracking-wide text-stone-400 uppercase">
                    {copy.currentRun}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-stone-700">
                    {snapshot.runTitle}
                  </p>
                </div>
              )}
            </div>
          </details>
        </aside>
      </main>
    </div>
  );
}

function StagePanel({
  stages,
  runStatus,
  copy,
}: {
  stages: ReturnType<typeof buildWarRoomSnapshot>["stages"];
  runStatus?: WarRoomRunStatus;
  copy: ReturnType<typeof useI18n>["t"]["warRoom"];
}) {
  if (stages.length === 0) return null;
  return (
    <div className="rounded-xl border border-white/90 bg-white/85 p-3 shadow-sm">
      <h3 className="mb-2 text-[10px] font-medium tracking-wide text-stone-400 uppercase">
        {copy.pipeline}
      </h3>
      <div className="space-y-1.5">
        {stages.map((stage) => (
          <div key={stage.id} className="flex items-center gap-2">
            <span
              className={cn(
                "size-2 shrink-0 rounded-full",
                stage.done
                  ? "bg-emerald-500"
                  : stage.current
                    ? "animate-pulse bg-amber-500"
                    : "bg-stone-200",
              )}
            />
            <span
              className={cn(
                "text-xs",
                stage.done
                  ? "text-stone-600"
                  : stage.current
                    ? "font-medium text-amber-700"
                    : "text-stone-400",
              )}
            >
              {stage.label}
            </span>
            {stage.current && runStatus === "running" && (
              <span className="ml-auto text-[10px] text-amber-500">
                {copy.running}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricsPanel({
  metrics,
  copy,
}: {
  metrics: ReturnType<typeof buildWarRoomSnapshot>["metrics"];
  copy: ReturnType<typeof useI18n>["t"]["warRoom"];
}) {
  const items = [
    { label: copy.metrics.llmCalls, value: String(metrics.llmCalls) },
    { label: copy.metrics.tokens, value: metrics.totalTokens.toLocaleString() },
    {
      label: copy.metrics.duration,
      value:
        metrics.durationSeconds !== undefined
          ? `${metrics.durationSeconds}s`
          : "—",
    },
    { label: copy.metrics.searches, value: String(metrics.webSearches) },
    { label: copy.metrics.fetches, value: String(metrics.webFetches) },
    { label: copy.metrics.filesWritten, value: String(metrics.writeFiles) },
  ];
  return (
    <div className="rounded-xl border border-white/90 bg-white/85 p-3 shadow-sm">
      <h3 className="mb-2 text-[10px] font-medium tracking-wide text-stone-400 uppercase">
        {copy.runMetrics}
      </h3>
      <div className="grid grid-cols-3 gap-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="rounded-lg bg-stone-50/80 px-2 py-1.5"
          >
            <div className="text-[10px] text-stone-400">{item.label}</div>
            <div className="text-sm font-semibold text-stone-700">
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TaskQueuePanel({
  actors,
  copy,
}: {
  actors: WarRoomActorSnapshot[];
  copy: ReturnType<typeof useI18n>["t"]["warRoom"];
}) {
  const subagents = actors.filter((a) => a.id !== "ecom-launch");
  return (
    <div className="rounded-xl border border-white/90 bg-white/85 p-3 shadow-sm">
      <h3 className="mb-2 text-[10px] font-medium tracking-wide text-stone-400 uppercase">
        {copy.taskQueue}
      </h3>
      <div className="space-y-1.5">
        {subagents.map((actor) => (
          <div
            key={actor.id}
            className="flex items-center gap-2 rounded-lg bg-stone-50/80 px-2 py-1.5"
          >
            <span
              className={cn(
                "size-2 shrink-0 rounded-full",
                actor.status === "working"
                  ? "animate-pulse bg-orange-500"
                  : actor.status === "done"
                    ? "bg-emerald-500"
                    : actor.status === "failed"
                      ? "bg-red-500"
                      : actor.status === "queued"
                        ? "bg-amber-400"
                        : "bg-stone-300",
              )}
            />
            <span className="w-16 shrink-0 truncate text-[11px] font-medium text-stone-600">
              {actor.name}
            </span>
            <span className="min-w-0 flex-1 truncate text-[10px] text-stone-400">
              {actor.task ?? copy.statuses[actor.status]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ArtifactsPanel({
  artifacts,
  copy,
}: {
  artifacts: Set<string>;
  copy: ReturnType<typeof useI18n>["t"]["warRoom"];
}) {
  return (
    <div className="rounded-xl border border-white/90 bg-white/85 p-3 shadow-sm">
      <h3 className="mb-2 text-[10px] font-medium tracking-wide text-stone-400 uppercase">
        {copy.artifactFiles(artifacts.size)}
      </h3>
      {artifacts.size > 0 ? (
        <div className="space-y-1">
          {[...artifacts].map((artifact) => (
            <div
              key={artifact}
              className="flex items-center gap-1.5 rounded-lg bg-stone-50/80 px-2 py-1"
            >
              <FileStackIcon className="size-3 shrink-0 text-amber-500" />
              <span className="truncate text-[11px] text-stone-600">
                {artifact}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-stone-400">{copy.noArtifacts}</p>
      )}
    </div>
  );
}
