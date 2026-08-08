import {
  CheckCircle2,
  CircleStop,
  Eye,
  FilePenLine,
  RefreshCw,
  Repeat2,
  Wrench,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";

import type { VerificationLoopContent } from "./demo-locales";

export function LaunchVerificationLoop({
  content,
}: {
  content: VerificationLoopContent;
}) {
  return (
    <div
      data-testid="agent-environment-loop"
      className="overflow-hidden rounded-[1.75rem] border border-stone-900/10 bg-stone-950 text-white shadow-[0_24px_70px_rgba(82,54,31,0.16)]"
    >
      <div className="flex flex-col gap-3 border-b border-white/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-amber-300 text-stone-950">
            <Repeat2 className="size-5" />
          </span>
          <div>
            <p className="text-[10px] font-black tracking-[0.18em] text-amber-300 uppercase">
              Agent ↔ Environment
            </p>
            <h3 className="mt-0.5 font-bold">{content.title}</h3>
          </div>
        </div>
        <Badge
          className="border-white/15 bg-white/8 text-white"
          variant="outline"
        >
          {content.budget}
        </Badge>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_0.92fr]">
          <article
            data-loop-round="1"
            className="rounded-2xl border border-rose-200/70 bg-white p-5 text-stone-900"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-black tracking-[0.16em] text-stone-500 uppercase">
                {content.firstRound.label}
              </span>
              <Badge
                className="border-rose-200 bg-rose-50 text-rose-800"
                variant="outline"
              >
                {content.firstRound.result}
              </Badge>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.14em] text-stone-400 uppercase">
                  <Wrench className="size-3.5" />
                  {content.firstRound.actionLabel}
                </div>
                <code className="mt-2 block rounded-lg bg-stone-950 px-3 py-2 text-xs text-amber-300">
                  {content.firstRound.action}
                </code>
              </div>
              <div>
                <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.14em] text-rose-700 uppercase">
                  <Eye className="size-3.5" />
                  {content.firstRound.observationLabel}
                </div>
                <ul className="mt-2 space-y-2 text-xs leading-5 text-stone-600">
                  {content.firstRound.violations.map((violation) => (
                    <li key={violation} className="flex gap-2">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-rose-500" />
                      <span>{violation}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </article>

          <article
            data-testid="loop-agent-decision"
            className="rounded-2xl border border-amber-300/35 bg-amber-300 p-5 text-stone-950"
          >
            <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.16em] uppercase">
              <FilePenLine className="size-4" />
              {content.decision.label}
            </div>
            <h4 className="mt-4 text-lg font-black">
              {content.decision.title}
            </h4>
            <p className="mt-2 text-sm leading-6 text-stone-800">
              {content.decision.basis}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-white/55 p-3">
                <p className="text-[9px] font-black tracking-[0.14em] uppercase">
                  {content.decision.filesLabel}
                </p>
                <ul className="mt-2 space-y-1 font-mono text-[11px]">
                  {content.decision.files.map((file) => (
                    <li key={file}>{file}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-xl bg-white/55 p-3">
                <p className="text-[9px] font-black tracking-[0.14em] uppercase">
                  {content.decision.toolsLabel}
                </p>
                <ul className="mt-2 space-y-1 font-mono text-[11px]">
                  {content.decision.tools.map((tool) => (
                    <li key={tool}>{tool}</li>
                  ))}
                </ul>
              </div>
            </div>
            <p className="mt-3 text-xs font-bold text-stone-700">
              {content.decision.unchanged}
            </p>
          </article>
        </div>

        <div className="grid gap-3 rounded-2xl border border-white/10 bg-white/[0.06] px-4 py-3 sm:grid-cols-[auto_1fr_auto] sm:items-center">
          <RefreshCw className="size-5 text-amber-300" />
          <div>
            <p className="text-[10px] font-black tracking-[0.16em] text-amber-300 uppercase">
              {content.rerun.label}
            </p>
            <p className="mt-0.5 text-xs text-stone-300">
              {content.rerun.action}
            </p>
          </div>
          <span className="hidden text-2xl text-white/30 sm:block">↺</span>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_0.72fr]">
          <article
            data-loop-round="2"
            className="rounded-2xl border border-emerald-200/70 bg-white p-5 text-stone-900"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-black tracking-[0.16em] text-stone-500 uppercase">
                {content.secondRound.label}
              </span>
              <Badge
                className="border-emerald-200 bg-emerald-50 text-emerald-800"
                variant="outline"
              >
                {content.secondRound.result}
              </Badge>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.14em] text-stone-400 uppercase">
                  <Wrench className="size-3.5" />
                  {content.secondRound.actionLabel}
                </div>
                <code className="mt-2 block rounded-lg bg-stone-950 px-3 py-2 text-xs text-amber-300">
                  {content.secondRound.action}
                </code>
              </div>
              <div>
                <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.14em] text-emerald-700 uppercase">
                  <Eye className="size-3.5" />
                  {content.secondRound.observationLabel}
                </div>
                <ul className="mt-2 grid gap-1.5 text-xs text-stone-600 sm:grid-cols-2">
                  {content.secondRound.checks.map((check) => (
                    <li key={check} className="flex items-center gap-2">
                      <CheckCircle2 className="size-3.5 shrink-0 text-emerald-600" />
                      <span>{check}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </article>

          <article
            data-testid="loop-stop-condition"
            className="rounded-2xl border border-emerald-400/25 bg-emerald-950 p-5"
          >
            <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.16em] text-emerald-300 uppercase">
              <CircleStop className="size-4" />
              {content.stop.label}
            </div>
            <h4 className="mt-4 text-xl font-black text-white">
              {content.stop.title}
            </h4>
            <p className="mt-2 text-sm leading-6 text-emerald-100/75">
              {content.stop.reason}
            </p>
            <ul className="mt-4 space-y-2 text-xs text-emerald-100/80">
              {content.stop.metrics.map((metric) => (
                <li key={metric} className="flex items-center gap-2">
                  <CheckCircle2 className="size-3.5 shrink-0 text-emerald-300" />
                  <span>{metric}</span>
                </li>
              ))}
            </ul>
          </article>
        </div>
      </div>
    </div>
  );
}
