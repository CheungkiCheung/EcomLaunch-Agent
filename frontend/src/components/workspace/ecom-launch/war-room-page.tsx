"use client";

import { ArrowRightIcon, FileTextIcon, RadioTowerIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { LaunchCrewRole } from "@/components/workspace/ecom-launch/launch-crew-activity-model";
import { buildLaunchCrewActivityModelFromThread } from "@/components/workspace/ecom-launch/use-launch-crew-activity-model";
import { buildWarRoomMotion } from "@/components/workspace/ecom-launch/war-room-motion";
import { WarRoomStage } from "@/components/workspace/ecom-launch/war-room-stage";
import { useI18n } from "@/core/i18n/hooks";
import { explainLastToolCall } from "@/core/tools/utils";
import { useThreadState } from "@/core/threads/hooks";
import type { AgentThreadState } from "@/core/threads/types";

const EMPTY_THREAD_VALUES: AgentThreadState = {
  title: "Launch War Room",
  messages: [],
  artifacts: [],
  todos: [],
};

export function EcomLaunchWarRoomPage() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const threadId = searchParams.get("threadId");
  const isMock = searchParams.get("mock") === "true";
  const [selectedAgentId, setSelectedAgentId] =
    useState<LaunchCrewRole>("launch-director");
  const [motionTick, setMotionTick] = useState(7);
  const threadState = useThreadState(threadId, {
    enabled: Boolean(threadId),
    isMock,
  });
  const threadValues = threadState.data ?? EMPTY_THREAD_VALUES;

  const model = useMemo(
    () =>
      buildLaunchCrewActivityModelFromThread({
        messages: threadValues.messages ?? [],
        threadValues,
        selectedAgentId,
        isStreaming: threadState.isFetching,
        explainAction: (task) =>
          task.latestMessage
            ? explainLastToolCall(task.latestMessage, t)
            : null,
      }),
    [selectedAgentId, t, threadState.isFetching, threadValues],
  );

  const selectedAgent = model.selectedAgent;
  const readyArtifacts = model.artifactStatuses
    .filter((artifact) => artifact.status === "ready")
    .slice(0, 5);
  const motionQueue = useMemo(
    () => buildWarRoomMotion(model.agents, motionTick),
    [model.agents, motionTick],
  );

  useEffect(() => {
    const id = window.setInterval(() => {
      setMotionTick((tick) => tick + 1);
    }, 3600);
    return () => window.clearInterval(id);
  }, []);

  return (
    <main
      aria-label="EcomLaunch full war room"
      className="flex h-screen min-h-0 flex-col overflow-hidden bg-[#f4eadb] text-slate-900"
    >
      <header className="border-b border-amber-900/10 bg-[#fff8ed]/95 px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs font-black tracking-[0.22em] text-teal-700/70 uppercase">
              EcomLaunch
            </div>
            <h1 className="mt-1 text-2xl leading-tight font-black">
              Launch War Room
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-600">
              {threadId
                ? `Synced with ${threadValues.title || "current EcomLaunch thread"}.`
                : "Open from an EcomLaunch chat to sync live tasks and artifacts into the room."}
            </p>
          </div>
          <Button variant="secondary" asChild>
            <Link
              href={
                threadId
                  ? `/workspace/agents/ecom-launch/chats/${threadId}${isMock ? "?mock=true" : ""}`
                  : "/workspace/agents/ecom-launch/chats/new"
              }
            >
              Open Chat
              <ArrowRightIcon />
            </Link>
          </Button>
        </div>
      </header>

      <section className="grid min-h-0 flex-1 grid-rows-[minmax(360px,52vh)_minmax(0,1fr)] overflow-y-auto lg:grid-cols-[minmax(0,1fr)_320px] lg:grid-rows-none lg:overflow-hidden">
        <div className="min-h-0 overflow-hidden p-4 lg:p-5">
          <div className="relative size-full overflow-hidden rounded-lg border border-amber-900/15 bg-[#efe7d8] shadow-[0_18px_40px_rgba(121,83,43,0.16)]">
            <WarRoomStage
              agents={model.agents}
              artifacts={model.artifactStatuses}
              motions={motionQueue}
              selectedAgentId={selectedAgentId}
              onSelectAgent={setSelectedAgentId}
            />
          </div>
        </div>

        <aside className="min-h-0 border-t border-amber-900/10 bg-[#fff8ed] lg:border-t-0 lg:border-l">
          <div className="flex h-full min-h-0 flex-col">
            <section className="border-b border-amber-900/10 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-black tracking-wide text-teal-700/70 uppercase">
                    Selected Agent
                  </div>
                  <h2 className="mt-1 text-lg font-black">
                    {selectedAgent.name}
                  </h2>
                  <p className="text-sm text-slate-600">{selectedAgent.desk}</p>
                </div>
                <Badge variant="secondary">{selectedAgent.status}</Badge>
              </div>
              <p className="mt-4 rounded-md border border-amber-900/10 bg-white/70 p-3 text-sm leading-6 text-slate-700">
                {selectedAgent.lastLine}
              </p>
            </section>

            <section className="border-b border-amber-900/10 p-5">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-slate-600">Crew progress</span>
                <span className="font-black">
                  {model.completedAgentCount}/
                  {Math.max(model.activeAgentCount, 1)}
                </span>
              </div>
              <Progress value={model.progress} className="h-1.5" />
            </section>

            <section className="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
              <div className="flex items-center gap-2 text-sm font-black text-slate-800">
                <RadioTowerIcon className="size-4 text-teal-700" />
                Live motion rules
              </div>
              {[
                "Desks, screens, and conveyors are fixed room props.",
                "Only standalone character sprites move across the room.",
                "Idle agents roam between room hotspots.",
                "Assigned agents return to their own station.",
                "Launch Director stays seated at the command console.",
              ].map((rule) => (
                <div
                  key={rule}
                  className="rounded-md border border-amber-900/10 bg-white/70 px-3 py-2 text-sm text-slate-600"
                >
                  {rule}
                </div>
              ))}

              <div className="pt-3">
                <div className="mb-2 text-sm font-black text-slate-800">
                  Motion queue
                </div>
                <div className="space-y-2">
                  {motionQueue.map((motion) => (
                    <div
                      key={motion.id}
                      className="flex items-center justify-between gap-3 rounded-md border border-amber-900/10 bg-white/70 px-3 py-2 text-xs"
                    >
                      <span className="min-w-0 truncate text-slate-600">
                        {motion.id}
                      </span>
                      <span className="shrink-0 font-black text-teal-700">
                        {motion.state}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-black text-slate-800">
                  <FileTextIcon className="size-4 text-teal-700" />
                  Artifacts
                </div>
                <div className="space-y-2" data-war-room-artifact-queue>
                  {readyArtifacts.length > 0 ? (
                    readyArtifacts.map((artifact) => (
                      <button
                        key={artifact.filepath}
                        type="button"
                        data-war-room-artifact={artifact.name}
                        className="flex w-full items-center justify-between gap-3 rounded-md border border-amber-900/10 bg-white/70 px-3 py-2 text-left text-xs transition-colors hover:border-teal-700/30 hover:bg-white"
                        onClick={() => setSelectedAgentId(artifact.role)}
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-black text-slate-800">
                            {artifact.label}
                          </span>
                          <span className="block truncate text-slate-500">
                            {artifact.name}
                          </span>
                        </span>
                        <span className="shrink-0 rounded border border-emerald-200/20 bg-emerald-300/10 px-2 py-1 font-black text-emerald-100">
                          ready
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="rounded-md border border-amber-900/10 bg-white/70 px-3 py-3 text-sm text-slate-500">
                      {threadId
                        ? "No delivered artifacts in this thread yet."
                        : "No thread synced. Open a chat, then jump into the War Room."}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
        </aside>
      </section>
    </main>
  );
}
