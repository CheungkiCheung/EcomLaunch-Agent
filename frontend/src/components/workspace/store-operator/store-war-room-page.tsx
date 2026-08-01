"use client";

import { ArrowLeftIcon, CircleDotIcon, Loader2Icon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useThreadState } from "@/core/threads/hooks";
import type { AgentThreadState } from "@/core/threads/types";
import { cn } from "@/lib/utils";

import {
  buildStoreCrewActivity,
  type StoreCrewRole,
} from "./store-crew-activity";
import { StoreWarRoomStage } from "./store-war-room-stage";

const EMPTY_THREAD: AgentThreadState = {
  title: "商铺运营",
  messages: [],
  artifacts: [],
  todos: [],
};

export function StoreWarRoomPage() {
  const searchParams = useSearchParams();
  const threadId = searchParams.get("threadId");
  const isMock = searchParams.get("mock") === "true";
  const [selectedRole, setSelectedRole] = useState<StoreCrewRole>("lead");
  const threadState = useThreadState(threadId, {
    enabled: Boolean(threadId),
    isMock,
    refetchInterval: threadId ? 1500 : false,
  });
  const thread = threadState.data ?? EMPTY_THREAD;
  const activity = useMemo(
    () => buildStoreCrewActivity(thread.messages ?? [], false),
    [thread.messages],
  );
  const selected =
    activity.agents.find((agent) => agent.id === selectedRole) ??
    activity.agents[0]!;

  return (
    <main className="min-h-screen bg-[#f5eee4] text-slate-900">
      <header className="border-b border-amber-900/10 bg-[#fffaf2]/95 px-4 py-3 backdrop-blur lg:px-6">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-[0.18em] text-teal-700 uppercase">
              运营现场
            </p>
            <h1 className="truncate text-xl font-bold">商铺运营作战室</h1>
            <p className="mt-0.5 truncate text-xs text-slate-500">
              {threadId
                ? thread.title || "当前商铺运营对话"
                : "从商铺运营对话进入后，人物状态会同步真实 Subagent Task。"}
            </p>
          </div>
          <Button variant="secondary" asChild>
            <Link
              href={
                threadId
                  ? `/workspace/agents/store-operator/chats/${threadId}${isMock ? "?mock=true" : ""}`
                  : "/workspace/agents/store-operator/chats/new"
              }
            >
              <ArrowLeftIcon />
              返回对话
            </Link>
          </Button>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1500px] gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_280px] lg:p-6">
        <section className="min-w-0">
          <StoreWarRoomStage
            agents={activity.agents}
            selectedRole={selectedRole}
            onSelectRole={setSelectedRole}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Badge variant="secondary">
              {activity.activeCount} 个角色工作中
            </Badge>
            <Badge variant="outline">
              {activity.completedCount} 个任务已完成
            </Badge>
            <span>未被调用的角色会保持空闲走动。</span>
          </div>
        </section>

        <aside className="rounded-lg border border-amber-900/10 bg-white/75 p-4 shadow-sm backdrop-blur">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-slate-500">当前角色</p>
              <h2 className="mt-1 text-base font-semibold">{selected.name}</h2>
              <p className="text-xs text-slate-500">{selected.desk}</p>
            </div>
            <Badge
              variant={selected.active ? "default" : "secondary"}
              className={cn(selected.active && "bg-teal-600 hover:bg-teal-600")}
            >
              {selected.active ? (
                <Loader2Icon className="animate-spin" />
              ) : (
                <CircleDotIcon />
              )}
              {selected.active ? "工作中" : "空闲"}
            </Badge>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-700">
            {selected.lastLine}
          </p>
          {selected.task && (
            <div className="mt-4 rounded-md bg-[#f6f1e8] p-3 text-xs leading-5 text-slate-600">
              <div className="font-medium text-slate-800">本轮任务</div>
              <p className="mt-1">{selected.task.description}</p>
            </div>
          )}
          <div className="mt-5 space-y-2">
            {activity.agents.map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => setSelectedRole(agent.id)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                  selectedRole === agent.id
                    ? "border-teal-500/30 bg-teal-50"
                    : "border-transparent bg-white/70 hover:bg-white",
                )}
              >
                <span>{agent.name}</span>
                <span
                  className={cn(
                    "size-2 rounded-full",
                    agent.active ? "bg-teal-500" : "bg-slate-300",
                  )}
                />
              </button>
            ))}
          </div>
        </aside>
      </div>
    </main>
  );
}
