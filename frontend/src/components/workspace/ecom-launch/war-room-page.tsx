"use client";

import { ArrowRightIcon, FileTextIcon, RadioTowerIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  buildLaunchCrewActivityModel,
  type LaunchCrewRole,
} from "@/components/workspace/ecom-launch/launch-crew-activity-model";
import { PixelOffice } from "@/components/workspace/ecom-launch/pixel-office";
import { buildWarRoomMotion } from "@/components/workspace/ecom-launch/war-room-motion";

export function EcomLaunchWarRoomPage() {
  const [selectedAgentId, setSelectedAgentId] =
    useState<LaunchCrewRole>("launch-director");

  const model = useMemo(
    () =>
      buildLaunchCrewActivityModel({
        tasks: [],
        artifacts: [],
        todos: [],
        selectedAgentId,
        isStreaming: false,
      }),
    [selectedAgentId],
  );

  const selectedAgent = model.selectedAgent;
  const motionQueue = useMemo(
    () => buildWarRoomMotion(model.agents, 2),
    [model.agents],
  );

  return (
    <main
      aria-label="EcomLaunch full war room"
      className="flex h-screen min-h-0 flex-col overflow-hidden bg-[#111815] text-slate-50"
    >
      <header className="border-b border-cyan-100/10 bg-[#0e1513]/95 px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs font-black tracking-[0.22em] text-cyan-200/60 uppercase">
              EcomLaunch
            </div>
            <h1 className="mt-1 text-2xl leading-tight font-black">
              Launch War Room
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-300">
              Agents roam the room while idle, return to their stations when
              assigned, and report back to the Director when work lands.
            </p>
          </div>
          <Button variant="secondary" asChild>
            <Link href="/workspace/agents/ecom-launch/chats/new">
              Open Chat
              <ArrowRightIcon />
            </Link>
          </Button>
        </div>
      </header>

      <section className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-h-0 overflow-hidden p-5">
          <div className="relative size-full overflow-hidden rounded-lg border border-cyan-100/15 bg-[#18241f] shadow-[0_0_48px_rgba(17,255,190,0.08)]">
            <PixelOffice
              agents={model.agents}
              className="size-full rounded-none border-0 shadow-none [&>div]:h-full"
              onSelectAgent={setSelectedAgentId}
            />
          </div>
        </div>

        <aside className="min-h-0 border-l border-cyan-100/10 bg-[#0f1715]">
          <div className="flex h-full min-h-0 flex-col">
            <section className="border-b border-cyan-100/10 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-black tracking-wide text-cyan-200/60 uppercase">
                    Selected Agent
                  </div>
                  <h2 className="mt-1 text-lg font-black">
                    {selectedAgent.name}
                  </h2>
                  <p className="text-sm text-slate-300">{selectedAgent.desk}</p>
                </div>
                <Badge variant="secondary">{selectedAgent.status}</Badge>
              </div>
              <p className="mt-4 rounded-md border border-cyan-100/10 bg-cyan-50/5 p-3 text-sm leading-6 text-slate-200">
                {selectedAgent.lastLine}
              </p>
            </section>

            <section className="border-b border-cyan-100/10 p-5">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-slate-300">Crew progress</span>
                <span className="font-black">
                  {model.completedAgentCount}/
                  {Math.max(model.activeAgentCount, 1)}
                </span>
              </div>
              <Progress value={model.progress} className="h-1.5" />
            </section>

            <section className="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
              <div className="flex items-center gap-2 text-sm font-black text-slate-200">
                <RadioTowerIcon className="size-4 text-cyan-200" />
                Live motion rules
              </div>
              {[
                "Idle agents roam between room hotspots.",
                "Assigned agents return to their own station.",
                "Launch Director stays seated at the command console.",
                "Completed work moves through the artifact conveyor.",
              ].map((rule) => (
                <div
                  key={rule}
                  className="rounded-md border border-cyan-100/10 bg-cyan-50/5 px-3 py-2 text-sm text-slate-300"
                >
                  {rule}
                </div>
              ))}

              <div className="pt-3">
                <div className="mb-2 text-sm font-black text-slate-200">
                  Motion queue
                </div>
                <div className="space-y-2">
                  {motionQueue.map((motion) => (
                    <div
                      key={motion.id}
                      className="flex items-center justify-between gap-3 rounded-md border border-cyan-100/10 bg-cyan-50/5 px-3 py-2 text-xs"
                    >
                      <span className="min-w-0 truncate text-slate-300">
                        {motion.id}
                      </span>
                      <span className="shrink-0 font-black text-cyan-100">
                        {motion.state}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-black text-slate-200">
                  <FileTextIcon className="size-4 text-cyan-200" />
                  Artifacts
                </div>
                <div className="rounded-md border border-cyan-100/10 bg-cyan-50/5 px-3 py-3 text-sm text-slate-400">
                  No deliverables yet. They will appear here as package drops
                  when agents report back.
                </div>
              </div>
            </section>
          </div>
        </aside>
      </section>
    </main>
  );
}
