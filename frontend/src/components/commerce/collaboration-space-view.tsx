"use client";

import {
  ArrowLeftIcon,
  BoxIcon,
  ChartNoAxesCombinedIcon,
  CircleAlertIcon,
  ClipboardCheckIcon,
  DatabaseIcon,
  FileCheck2Icon,
  LoaderCircleIcon,
  PackageCheckIcon,
  ShieldCheckIcon,
  WrenchIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import type {
  CommerceCollaborationActorViewModel,
  CommerceCollaborationSceneViewModel,
  CommerceCollaborationStation,
} from "@/core/commerce/collaboration-scene-view-model";
import { cn } from "@/lib/utils";

import {
  COMMERCE_COLLABORATION_ROOM_SPRITE,
  commerceActorPlacement,
  commerceActorSprite,
  commerceStationSprite,
} from "./collaboration-space-assets";

export function CommerceCollaborationSpaceView({
  scene,
  title,
  threadId,
  runId,
  backHref,
  selectedTaskId,
  isLoading,
  error,
  onSelectTask,
}: {
  scene: CommerceCollaborationSceneViewModel;
  title: string;
  threadId: string | null;
  runId: string | null;
  backHref: string;
  selectedTaskId: string | null;
  isLoading: boolean;
  error: Error | null;
  onSelectTask: (taskId: string | null) => void;
}) {
  const selectedActor =
    scene.actors.find((actor) => actor.taskId === selectedTaskId) ?? null;

  return (
    <div className="flex size-full min-h-0 flex-col bg-[#f7f6f2] text-stone-900">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-stone-200/90 bg-white/90 px-4 backdrop-blur md:px-6">
        <Button variant="ghost" size="sm" asChild>
          <Link href={backHref}>
            <ArrowLeftIcon />
            返回对话
          </Link>
        </Button>
        <div className="h-5 w-px bg-stone-200" />
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold">{title}</h1>
          <p className="truncate text-[11px] text-stone-500">
            协作空间
            {runId ? ` · 运行 ${shortId(runId)}` : " · 尚无运行"}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {isLoading && (
            <LoaderCircleIcon
              className="size-3.5 animate-spin text-stone-500 motion-reduce:animate-none"
              aria-label="正在读取任务事件"
            />
          )}
          <span
            aria-label={scene.statusText}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap",
              sceneStatusClass(scene.sceneStatus),
            )}
          >
            <span className="size-1.5 rounded-full bg-current opacity-70" />
            <span className="hidden sm:inline">{scene.statusText}</span>
            <span className="sm:hidden">
              {compactSceneStatusText(scene.sceneStatus)}
            </span>
          </span>
        </div>
      </header>

      <main className="relative min-h-0 flex-1 overflow-auto p-3 md:p-5">
        <section
          className="relative mx-auto min-h-[620px] w-full max-w-[1440px] overflow-hidden rounded-3xl border border-stone-200 bg-[#eee9df] shadow-[0_24px_80px_-48px_rgba(41,37,36,0.45)]"
          data-commerce-collaboration-scene
        >
          <Image
            src={COMMERCE_COLLABORATION_ROOM_SPRITE}
            alt=""
            fill
            priority
            sizes="(min-width: 1440px) 1440px, 100vw"
            className="object-cover object-center"
            data-commerce-room-sprite={COMMERCE_COLLABORATION_ROOM_SPRITE}
            aria-hidden="true"
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,.08),rgba(248,246,240,.18)_58%,rgba(244,240,232,.36))]" />
          <div className="absolute top-[5%] left-[4%] rounded-2xl border border-white/80 bg-white/78 px-4 py-3 shadow-sm backdrop-blur-md">
            <p className="text-[11px] font-medium tracking-[0.16em] text-stone-500">
              电商智能体协作台
            </p>
            <p className="mt-1 text-sm font-semibold">真实任务协作现场</p>
          </div>

          {error && (
            <div className="absolute inset-x-6 top-24 z-30 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              协作任务读取失败：{error.message}
            </div>
          )}

          {!isLoading && scene.actors.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
              <div className="max-w-sm rounded-3xl border border-white/90 bg-white/80 px-8 py-9 shadow-sm backdrop-blur">
                <BoxIcon className="mx-auto size-8 text-stone-400" />
                <h2 className="mt-4 text-base font-semibold">
                  当前没有真实协作任务
                </h2>
                <p className="mt-2 text-sm leading-6 text-stone-500">
                  回到对话上传数据并提出问题。主智能体只有在任务确实需要隔离调查或独立核验时，才会动态派遣子任务。
                </p>
                <Button className="mt-5" variant="outline" asChild>
                  <Link href={backHref}>返回当前对话</Link>
                </Button>
              </div>
            </div>
          )}

          {scene.actors.map((actor, index) => {
            const position = commerceActorPlacement(
              index,
              scene.actors.length,
              actor.placementKey,
            );
            const actorSprite = commerceActorSprite(actor.profile);
            const stationSprite = commerceStationSprite(actor.station);
            return (
              <div
                key={actor.taskId}
                className="pointer-events-none absolute z-10 h-[260px] w-[176px] -translate-x-1/2 -translate-y-1/2 scale-[.68] sm:w-[204px] sm:scale-[.84] md:h-[286px] md:w-[236px] md:scale-100"
                style={{
                  left: `${position.left}%`,
                  top: `${position.top}%`,
                }}
                data-commerce-task-station={actor.taskId}
              >
                <div className="absolute inset-x-1 top-0 h-[166px] rounded-[30px] border border-white/80 bg-white/34 shadow-[0_20px_36px_-30px_rgba(41,37,36,0.75)] backdrop-blur-[2px] md:h-[188px]">
                  <div className="absolute top-2 left-2 z-10 inline-flex items-center gap-1.5 rounded-full border border-white/90 bg-white/88 px-2 py-1 text-[10px] font-medium text-stone-600 shadow-sm backdrop-blur">
                    <StationIcon station={actor.station} className="size-3" />
                    {stationLabel(actor.station)}
                  </div>
                  <Image
                    src={stationSprite}
                    alt=""
                    fill
                    sizes="(min-width: 768px) 220px, 170px"
                    className={cn(
                      "object-contain object-center p-3 pt-7 drop-shadow-[0_16px_12px_rgba(77,58,36,0.13)]",
                      stationImageStateClass(actor.status),
                    )}
                    data-commerce-station-sprite={stationSprite}
                    aria-hidden="true"
                  />
                  {actor.propLabel && (
                    <span className="absolute right-2 bottom-2 z-10 max-w-[75%] truncate rounded-md border border-white/90 bg-white/92 px-1.5 py-0.5 text-[9px] font-medium text-stone-600 shadow-sm">
                      正在使用：{actor.propLabel}
                    </span>
                  )}
                </div>

                <button
                  type="button"
                  className={cn(
                    "group pointer-events-auto absolute inset-x-1 bottom-0 z-10 text-left transition-transform outline-none hover:scale-[1.03] focus-visible:rounded-2xl focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 motion-reduce:transition-none md:inset-x-4",
                    selectedActor?.taskId === actor.taskId && "scale-[1.04]",
                  )}
                  onClick={() => onSelectTask(actor.taskId)}
                  aria-label={actor.ariaLabel}
                  data-commerce-actor={actor.actorId}
                  data-commerce-task-id={actor.taskId}
                  data-commerce-task-status={actor.status}
                  data-commerce-station={actor.station}
                  data-commerce-motion={actor.motion}
                >
                  <div
                    className={cn(
                      "relative mx-auto h-[126px] w-[96px] origin-bottom md:h-[144px] md:w-[110px]",
                      actorImageStateClass(actor),
                    )}
                    aria-hidden="true"
                  >
                    <div className="absolute right-2 bottom-1 left-2 h-3 rounded-[50%] bg-stone-900/16 blur-[3px]" />
                    <Image
                      src={actorSprite}
                      alt=""
                      fill
                      sizes="(min-width: 768px) 110px, 96px"
                      className="object-contain object-bottom drop-shadow-[0_12px_8px_rgba(41,37,36,0.16)]"
                      data-commerce-actor-sprite={actorSprite}
                    />
                    <span
                      className={cn(
                        "absolute right-0 bottom-2 size-3 rounded-full border-2 border-white shadow-sm",
                        actorStatusDotClass(actor.status),
                      )}
                    />
                  </div>

                  <div className="relative -mt-3 rounded-2xl border border-white/90 bg-white/94 px-3 py-2.5 shadow-md backdrop-blur-md">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-semibold">
                        {actor.profileLabel}
                      </span>
                      <span
                        className={cn(
                          "ml-auto size-2 rounded-full",
                          actorStatusDotClass(actor.status),
                        )}
                      />
                    </div>
                    <p className="mt-1 truncate text-[11px] text-stone-500">
                      {actor.detailLabel}
                    </p>
                    {actor.propLabel && (
                      <span className="mt-1.5 inline-flex rounded-md bg-stone-100 px-1.5 py-0.5 text-[10px] text-stone-600">
                        {actor.propLabel}
                      </span>
                    )}
                  </div>
                </button>
              </div>
            );
          })}

          {selectedActor && (
            <aside
              className="absolute top-20 right-4 z-30 w-[280px] rounded-2xl border border-white/90 bg-white/94 p-4 shadow-xl backdrop-blur md:right-6"
              data-commerce-actor-drawer
            >
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-stone-100 p-2">
                  <StationIcon
                    station={selectedActor.station}
                    className="size-4 text-stone-600"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-medium tracking-[0.15em] text-stone-400 uppercase">
                    当前任务详情
                  </p>
                  <h2 className="mt-1 truncate text-sm font-semibold">
                    {selectedActor.title}
                  </h2>
                </div>
                <button
                  type="button"
                  className="rounded-md px-1.5 py-0.5 text-xs text-stone-400 hover:bg-stone-100 hover:text-stone-700"
                  onClick={() => onSelectTask(null)}
                  aria-label="关闭任务详情"
                >
                  关闭
                </button>
              </div>
              <dl className="mt-4 grid grid-cols-[76px_1fr] gap-x-3 gap-y-2 text-xs">
                <dt className="text-stone-400">角色</dt>
                <dd>{selectedActor.profileLabel}</dd>
                <dt className="text-stone-400">状态</dt>
                <dd>{selectedActor.statusLabel}</dd>
                <dt className="text-stone-400">当前活动</dt>
                <dd>{selectedActor.detailLabel}</dd>
                {selectedActor.propLabel && (
                  <>
                    <dt className="text-stone-400">使用道具</dt>
                    <dd>{selectedActor.propLabel}</dd>
                  </>
                )}
              </dl>
              {selectedActor.messagePreview && (
                <p className="mt-3 rounded-lg bg-stone-100 px-3 py-2 text-xs leading-5 text-stone-600">
                  {selectedActor.messagePreview}
                </p>
              )}
              <details className="group mt-3 border-t border-stone-200 pt-3 text-xs">
                <summary className="cursor-pointer list-none font-medium text-stone-500 hover:text-stone-800 [&::-webkit-details-marker]:hidden">
                  <span className="group-open:hidden">查看审计信息</span>
                  <span className="hidden group-open:inline">收起审计信息</span>
                </summary>
                <dl className="mt-3 grid grid-cols-[76px_1fr] gap-x-3 gap-y-2">
                  <dt className="text-stone-400">任务编号</dt>
                  <dd className="truncate font-mono text-[11px]">
                    {selectedActor.taskId}
                  </dd>
                  <dt className="text-stone-400">技能</dt>
                  <dd>{selectedActor.availableSkills.length} 个</dd>
                  <dt className="text-stone-400">工具权限</dt>
                  <dd>{selectedActor.availableTools.length} 个</dd>
                  <dt className="text-stone-400">事件序号</dt>
                  <dd>{selectedActor.lastEventSeq}</dd>
                </dl>
              </details>
            </aside>
          )}

          {scene.actors.length > 0 && (
            <div className="absolute right-4 bottom-4 left-4 z-20 flex gap-2 overflow-x-auto rounded-2xl border border-white/90 bg-white/86 p-2 shadow-md backdrop-blur md:right-6 md:left-6">
              {scene.actors.map((actor) => (
                <button
                  type="button"
                  key={`event-${actor.taskId}`}
                  className="flex min-w-fit items-center gap-2 rounded-xl px-2.5 py-2 text-left hover:bg-stone-100"
                  onClick={() => onSelectTask(actor.taskId)}
                >
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      actorStatusDotClass(actor.status),
                    )}
                  />
                  <span className="text-xs font-medium">
                    {actor.profileLabel}
                  </span>
                  <span className="text-[11px] text-stone-400">
                    {actor.statusLabel}
                  </span>
                </button>
              ))}
              <span className="ml-auto self-center pr-2 text-[11px] text-stone-400">
                共 {scene.actors.length} 个真实任务
              </span>
            </div>
          )}
        </section>

        {scene.hasProjectionWarnings && (
          <div className="mx-auto mt-3 flex w-full max-w-[1440px] items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            <CircleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
            <div>
              {scene.projectionWarnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className="flex min-h-9 shrink-0 flex-col items-start gap-1 border-t border-stone-200 bg-white/80 px-4 py-2 text-[11px] text-stone-500 sm:flex-row sm:items-center sm:justify-between md:px-6">
        <span>人物与动作来自真实任务/事件；无任务时不显示角色</span>
        <span className="font-mono">
          {threadId ? `对话 ${shortId(threadId)}` : "未绑定对话"}
        </span>
      </footer>
    </div>
  );
}

function stationLabel(station: CommerceCollaborationStation) {
  return {
    intake: "数据接入工位",
    analysis: "指标分析工位",
    verification: "证据核验工位",
    action: "行动执行工位",
    approval: "人工审批工位",
    delivery: "结果交付工位",
    recovery: "异常恢复工位",
    general: "通用协作工位",
  }[station];
}

function actorImageStateClass(actor: CommerceCollaborationActorViewModel) {
  if (actor.status === "working") {
    return "animate-pulse motion-reduce:animate-none";
  }
  if (["queued", "waiting", "approval"].includes(actor.status)) {
    return "opacity-85";
  }
  if (["failed", "cancelled", "timed_out"].includes(actor.status)) {
    return "grayscale-[.45] opacity-80";
  }
  if (actor.status === "blocked") {
    return "grayscale-[.25] opacity-85";
  }
  return "";
}

function stationImageStateClass(
  status: CommerceCollaborationActorViewModel["status"],
) {
  if (status === "working") {
    return "drop-shadow-[0_0_18px_rgba(14,165,233,0.18)]";
  }
  if (["failed", "cancelled", "timed_out"].includes(status)) {
    return "grayscale-[.5] opacity-75";
  }
  if (["queued", "waiting", "approval", "blocked"].includes(status)) {
    return "opacity-85";
  }
  return "";
}

function actorStatusDotClass(
  status: CommerceCollaborationActorViewModel["status"],
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

function sceneStatusClass(
  status: CommerceCollaborationSceneViewModel["sceneStatus"],
) {
  return {
    empty: "border-stone-200 bg-stone-50 text-stone-600",
    active: "border-sky-200 bg-sky-50 text-sky-700",
    waiting: "border-amber-200 bg-amber-50 text-amber-800",
    blocked: "border-orange-200 bg-orange-50 text-orange-800",
    completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
    failed: "border-rose-200 bg-rose-50 text-rose-700",
  }[status];
}

function compactSceneStatusText(
  status: CommerceCollaborationSceneViewModel["sceneStatus"],
) {
  return {
    empty: "无任务",
    active: "协作中",
    waiting: "等待中",
    blocked: "已阻塞",
    completed: "已完成",
    failed: "失败",
  }[status];
}

function StationIcon({
  station,
  className,
}: {
  station: CommerceCollaborationStation;
  className?: string;
}) {
  const Icon = {
    intake: DatabaseIcon,
    analysis: ChartNoAxesCombinedIcon,
    verification: ShieldCheckIcon,
    action: WrenchIcon,
    approval: ClipboardCheckIcon,
    delivery: PackageCheckIcon,
    recovery: FileCheck2Icon,
    general: BoxIcon,
  }[station];
  return <Icon className={className} />;
}

function shortId(value: string) {
  return value.length <= 12 ? value : `${value.slice(0, 6)}…${value.slice(-4)}`;
}
