"use client";

import { ArrowRightIcon, FileTextIcon, RadioTowerIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  buildLaunchCrewActivityModel,
  type LaunchCrewTask,
  type LaunchCrewRole,
} from "@/components/workspace/ecom-launch/launch-crew-activity-model";
import { buildWarRoomMotion } from "@/components/workspace/ecom-launch/war-room-motion";
import { WarRoomStage } from "@/components/workspace/ecom-launch/war-room-stage";

const DEMO_TASKS: LaunchCrewTask[] = [
  {
    id: "demo-market",
    role: "market-voc-researcher",
    status: "completed",
    description: "Cluster public demand signals for the launch wedge.",
    prompt: "Find competitor, VOC, and marketplace signal clusters.",
    result: "Competitor table and VOC clusters are ready.",
  },
  {
    id: "demo-offer",
    role: "offer-architect",
    status: "in_progress",
    description: "Shape the first testable offer from evidence.",
    prompt: "Turn research into positioning.",
    currentAction: "Refining the first wedge and proof points.",
    toolName: "write_file",
  },
  {
    id: "demo-asset",
    role: "asset-studio",
    status: "completed",
    description: "Prepare listing copy and launch creative package.",
    prompt: "Draft listing pack and content assets.",
    result: "Listing package dropped on the conveyor.",
  },
];

const DEMO_ARTIFACTS = [
  "competitor-table.csv",
  "positioning-brief.md",
  "listing-pack.md",
];

export function EcomLaunchWarRoomPage() {
  const [selectedAgentId, setSelectedAgentId] =
    useState<LaunchCrewRole>("launch-director");
  const [motionTick, setMotionTick] = useState(7);

  const model = useMemo(
    () =>
      buildLaunchCrewActivityModel({
        tasks: DEMO_TASKS,
        artifacts: DEMO_ARTIFACTS,
        todos: [],
        selectedAgentId,
        isStreaming: false,
      }),
    [selectedAgentId],
  );

  const selectedAgent = model.selectedAgent;
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
            <WarRoomStage
              agents={model.agents}
              artifacts={model.artifactStatuses}
              motions={motionQueue}
              selectedAgentId={selectedAgentId}
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
                "Desks, screens, and conveyors are fixed room props.",
                "Only standalone character sprites move across the room.",
                "Idle agents roam between room hotspots.",
                "Assigned agents return to their own station.",
                "Launch Director stays seated at the command console.",
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
                <div className="space-y-2" data-war-room-artifact-queue>
                  {model.artifactStatuses
                    .filter((artifact) => artifact.status === "ready")
                    .slice(0, 5)
                    .map((artifact) => (
                      <button
                        key={artifact.filepath}
                        type="button"
                        data-war-room-artifact={artifact.name}
                        className="flex w-full items-center justify-between gap-3 rounded-md border border-cyan-100/10 bg-cyan-50/5 px-3 py-2 text-left text-xs transition-colors hover:border-cyan-100/30 hover:bg-cyan-50/10"
                        onClick={() => setSelectedAgentId(artifact.role)}
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-black text-slate-100">
                            {artifact.label}
                          </span>
                          <span className="block truncate text-slate-400">
                            {artifact.name}
                          </span>
                        </span>
                        <span className="shrink-0 rounded border border-emerald-200/20 bg-emerald-300/10 px-2 py-1 font-black text-emerald-100">
                          ready
                        </span>
                      </button>
                    ))}
                </div>
              </div>
            </section>
          </div>
        </aside>
      </section>
    </main>
  );
}
