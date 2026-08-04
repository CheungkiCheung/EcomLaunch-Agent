import {
  ArrowRight,
  CheckCircle2,
  CirclePause,
  ExternalLink,
  FileText,
  Github,
  KeyRound,
  PlayCircle,
  Radio,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "OpenSKU English Demo — No API Key Required",
  description:
    "Explore a recorded OpenSKU ecommerce validation run with the War Room, agent states, and sample deliverables.",
};

const actors = [
  {
    id: "ecom-launch",
    name: "Launch Director",
    status: "Done",
    activity: "Decision pack assembled",
    left: 48,
    top: 42,
    color: "#f2b35f",
  },
  {
    id: "market-voc-researcher",
    name: "Market Researcher",
    status: "Done",
    activity: "Sample signal map prepared",
    left: 14,
    top: 37,
    color: "#e98b63",
  },
  {
    id: "offer-architect",
    name: "Offer Architect",
    status: "Done",
    activity: "Positioning hypothesis drafted",
    left: 40,
    top: 25,
    color: "#d87855",
  },
  {
    id: "asset-studio",
    name: "Asset Studio",
    status: "Done",
    activity: "Listing pack created",
    left: 31,
    top: 75,
    color: "#ca6d67",
  },
  {
    id: "evidence-checker",
    name: "Evidence Checker",
    status: "Done",
    activity: "Claim boundaries reviewed",
    left: 64,
    top: 37,
    color: "#b76555",
  },
  {
    id: "data-inspector",
    name: "Growth Analyst",
    status: "Not used",
    activity: "No store dataset in this brief",
    left: 72,
    top: 80,
    color: "#78a99d",
  },
] as const;

const deliverables = [
  {
    title: "Launch decision",
    description:
      "A bounded validate-before-commit recommendation with explicit decision gates.",
    href: "/demo/opensku-coffee-mug/launch-decision.md",
    label: "DECISION",
  },
  {
    title: "Evidence ledger",
    description:
      "A sample ledger separating fixture observations, estimates, and assumptions.",
    href: "/demo/opensku-coffee-mug/evidence-ledger.md",
    label: "EVIDENCE",
  },
  {
    title: "Listing pack",
    description:
      "Draft positioning, bullets, objections, and content angles ready for editing.",
    href: "/demo/opensku-coffee-mug/listing-pack.md",
    label: "ASSETS",
  },
  {
    title: "Seven-day validation plan",
    description:
      "A low-cost sequence of tests with thresholds and stop conditions.",
    href: "/demo/opensku-coffee-mug/seven-day-validation-plan.md",
    label: "PLAN",
  },
] as const;

function ActorSprite({ actor }: { actor: (typeof actors)[number] }) {
  return (
    <div
      className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
      style={{ left: `${actor.left}%`, top: `${actor.top}%` }}
    >
      <div
        role="img"
        aria-label={`${actor.name}: ${actor.status}`}
        className="mx-auto h-[54px] w-9 bg-left-top bg-no-repeat drop-shadow-[0_5px_4px_rgba(74,45,26,0.35)]"
        style={{
          backgroundImage: `url(/war-room-original/characters/${actor.id}.png)`,
          backgroundSize: "144px 54px",
          imageRendering: "pixelated",
        }}
      />
      <div className="mt-1 hidden -translate-x-[calc(50%-18px)] rounded-full border border-white/75 bg-stone-950/75 px-2 py-0.5 text-[9px] font-semibold whitespace-nowrap text-white shadow-sm backdrop-blur-sm sm:block">
        {actor.name}
      </div>
    </div>
  );
}

export default function DemoPage() {
  return (
    <main className="min-h-screen bg-[#f3eadc] text-stone-900">
      <header className="sticky top-0 z-30 border-b border-stone-900/10 bg-[#f8f1e7]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
          <Link href="/" className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-stone-900 text-sm font-black text-amber-300">
              OS
            </span>
            <span>
              <span className="block text-sm font-bold tracking-tight">
                OpenSKU
              </span>
              <span className="block text-[10px] font-medium tracking-[0.18em] text-stone-500 uppercase">
                Recorded demo
              </span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Button
              asChild
              variant="ghost"
              size="sm"
              className="hidden sm:flex"
            >
              <a href="#deliverables">Sample outputs</a>
            </Button>
            <Button
              asChild
              size="sm"
              className="bg-stone-900 text-white hover:bg-stone-800"
            >
              <a
                href="https://github.com/CheungkiCheung/opensku"
                target="_blank"
                rel="noreferrer"
              >
                <Github />
                GitHub
              </a>
            </Button>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden border-b border-stone-900/10">
        <div className="absolute -top-40 right-[-10%] size-[520px] rounded-full bg-orange-300/35 blur-3xl" />
        <div className="absolute bottom-[-55%] left-[-8%] size-[520px] rounded-full bg-amber-200/60 blur-3xl" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-5 py-16 lg:grid-cols-[1.25fr_0.75fr] lg:px-8 lg:py-24">
          <div>
            <Badge
              className="border-orange-300/80 bg-orange-100 text-orange-900"
              variant="outline"
            >
              <PlayCircle />
              ENGLISH SAMPLE · NO API KEY
            </Badge>
            <h1 className="mt-6 max-w-4xl text-4xl leading-[1.05] font-black tracking-[-0.04em] text-stone-950 sm:text-6xl">
              See an ecommerce launch team turn one brief into a decision pack.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-stone-600">
              This deterministic OpenSKU walkthrough validates a hypothetical
              compact travel coffee mug for the US market. Explore the War Room,
              inspect every agent state, and open the resulting sample files.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                asChild
                size="lg"
                className="bg-orange-600 text-white hover:bg-orange-700"
              >
                <a href="#war-room">
                  Explore the War Room
                  <ArrowRight />
                </a>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-stone-400/70 bg-white/50"
              >
                <a
                  href="/demo/opensku-coffee-mug/launch-decision.md"
                  target="_blank"
                  rel="noreferrer"
                >
                  Read the decision
                  <ExternalLink />
                </a>
              </Button>
            </div>
          </div>

          <aside className="rounded-[2rem] border border-white/80 bg-white/65 p-6 shadow-[0_24px_70px_rgba(94,62,34,0.13)] backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold tracking-[0.18em] text-stone-500 uppercase">
                Sample brief
              </span>
              <Badge className="bg-amber-100 text-amber-900">VALIDATE</Badge>
            </div>
            <h2 className="mt-5 text-2xl font-bold tracking-tight">
              Compact travel coffee mug
            </h2>
            <dl className="mt-6 grid gap-4 text-sm">
              <div className="grid grid-cols-[92px_1fr] gap-3 border-t border-stone-900/10 pt-4">
                <dt className="font-medium text-stone-500">Market</dt>
                <dd className="font-semibold">United States</dd>
              </div>
              <div className="grid grid-cols-[92px_1fr] gap-3 border-t border-stone-900/10 pt-4">
                <dt className="font-medium text-stone-500">Audience</dt>
                <dd className="font-semibold">
                  Commuters and frequent travelers
                </dd>
              </div>
              <div className="grid grid-cols-[92px_1fr] gap-3 border-t border-stone-900/10 pt-4">
                <dt className="font-medium text-stone-500">Price test</dt>
                <dd className="font-semibold">$24–$34 hypothesis</dd>
              </div>
              <div className="grid grid-cols-[92px_1fr] gap-3 border-t border-stone-900/10 pt-4">
                <dt className="font-medium text-stone-500">Constraint</dt>
                <dd className="font-semibold">
                  Leak-resistant and under 350 g
                </dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-8 lg:px-8">
        <div
          data-testid="recorded-demo-notice"
          className="grid gap-4 rounded-2xl border border-amber-800/15 bg-amber-50/70 p-5 sm:grid-cols-[auto_1fr_auto] sm:items-center"
        >
          <div className="grid size-11 place-items-center rounded-xl bg-amber-200/70 text-amber-900">
            <Radio className="size-5" />
          </div>
          <div>
            <p className="font-bold text-amber-950">
              Recorded sample — no live agents are running
            </p>
            <p className="mt-1 text-sm leading-6 text-amber-900/75">
              All findings and metrics on this page are deterministic demo
              fixtures. They are not current market research and no model,
              provider, or external API is called.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-bold text-amber-900">
            <KeyRound className="size-4" />0 keys required
          </div>
        </div>
      </section>

      <section
        id="war-room"
        className="mx-auto max-w-7xl px-5 py-12 lg:px-8 lg:py-16"
      >
        <div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <span className="text-xs font-black tracking-[0.2em] text-orange-700 uppercase">
              01 · War Room replay
            </span>
            <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
              One room. Six visible responsibilities.
            </h2>
          </div>
          <div className="flex gap-2 text-xs font-semibold">
            <span className="rounded-full bg-emerald-100 px-3 py-1.5 text-emerald-800">
              5 completed
            </span>
            <span className="rounded-full bg-stone-200 px-3 py-1.5 text-stone-700">
              1 not used
            </span>
            <span className="rounded-full bg-sky-100 px-3 py-1.5 text-sky-800">
              4 artifacts
            </span>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
          <div
            id="demo-war-room"
            data-testid="demo-war-room"
            className="relative aspect-[1492/1054] overflow-hidden rounded-[1.75rem] border-4 border-white/70 bg-[#d7bda2] shadow-[0_24px_70px_rgba(82,54,31,0.2)]"
          >
            <div
              className="absolute inset-0 bg-cover bg-center"
              style={{
                backgroundImage: "url(/war-room-original/office-map.png)",
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-stone-950/15 via-transparent to-amber-50/10" />
            {actors.map((actor) => (
              <ActorSprite key={actor.id} actor={actor} />
            ))}
            <div className="absolute top-3 left-3 rounded-xl border border-white/60 bg-stone-950/70 px-3 py-2 text-white shadow-lg backdrop-blur-md sm:top-5 sm:left-5">
              <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.16em] text-amber-300 uppercase">
                <Sparkles className="size-3" />
                Replay complete
              </div>
              <p className="mt-1 hidden text-xs text-white/75 sm:block">
                Compact travel mug validation
              </p>
            </div>
          </div>

          <div
            data-testid="demo-agent-status"
            className="rounded-[1.75rem] border border-white/80 bg-white/65 p-4 shadow-[0_18px_55px_rgba(82,54,31,0.12)] backdrop-blur-xl"
          >
            <div className="flex items-center justify-between px-2 py-2">
              <div>
                <p className="text-xs font-black tracking-[0.18em] text-stone-500 uppercase">
                  Agent status
                </p>
                <p className="mt-1 text-sm text-stone-500">
                  Final state of this sample run
                </p>
              </div>
              <ShieldCheck className="size-6 text-emerald-700" />
            </div>
            <div className="mt-2 space-y-2">
              {actors.map((actor) => {
                const complete = actor.status === "Done";
                return (
                  <div
                    key={actor.id}
                    data-agent-id={actor.id}
                    className="flex items-center gap-3 rounded-xl border border-stone-900/8 bg-white/80 p-3"
                  >
                    <div
                      className="grid size-9 shrink-0 place-items-center rounded-xl"
                      style={{
                        backgroundColor: `${actor.color}22`,
                        color: actor.color,
                      }}
                    >
                      {complete ? (
                        <CheckCircle2 className="size-4" />
                      ) : (
                        <CirclePause className="size-4" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm font-bold">
                          {actor.name}
                        </p>
                        <span
                          className={
                            complete
                              ? "text-[10px] font-black text-emerald-700 uppercase"
                              : "text-[10px] font-black text-stone-500 uppercase"
                          }
                        >
                          {actor.status}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-stone-500">
                        {actor.activity}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section
        id="deliverables"
        className="border-y border-stone-900/10 bg-stone-950 text-white"
      >
        <div className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr]">
            <div>
              <span className="text-xs font-black tracking-[0.2em] text-amber-300 uppercase">
                02 · Inspect the output
              </span>
              <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">
                Not just a chat answer.
              </h2>
              <p className="mt-5 max-w-md leading-7 text-stone-300">
                Open each file to inspect the structure OpenSKU uses for
                decisions, evidence boundaries, launch assets, and validation
                steps.
              </p>
              <div className="mt-8 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-3xl font-black text-amber-300">4</p>
                  <p className="mt-1 text-stone-400">editable files</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-3xl font-black text-amber-300">0</p>
                  <p className="mt-1 text-stone-400">live API calls</p>
                </div>
              </div>
            </div>

            <div
              data-testid="demo-deliverables"
              className="grid gap-3 sm:grid-cols-2"
            >
              {deliverables.map((deliverable) => (
                <a
                  key={deliverable.href}
                  href={deliverable.href}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex min-h-48 flex-col rounded-2xl border border-white/10 bg-white/[0.06] p-5 transition hover:-translate-y-1 hover:border-amber-300/60 hover:bg-white/10"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black tracking-[0.18em] text-amber-300">
                      {deliverable.label}
                    </span>
                    <FileText className="size-5 text-stone-500 transition group-hover:text-amber-300" />
                  </div>
                  <h3 className="mt-8 text-xl font-bold">
                    {deliverable.title}
                  </h3>
                  <p className="mt-2 grow text-sm leading-6 text-stone-400">
                    {deliverable.description}
                  </p>
                  <div className="mt-5 flex items-center gap-2 text-sm font-bold text-white">
                    Open file
                    <ExternalLink className="size-3.5" />
                  </div>
                </a>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-24">
        <div className="rounded-[2rem] bg-gradient-to-br from-orange-600 to-amber-500 p-8 text-white shadow-[0_28px_80px_rgba(194,92,25,0.25)] sm:p-12">
          <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <p className="text-xs font-black tracking-[0.2em] text-orange-100 uppercase">
                Run the real workflow
              </p>
              <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
                Bring your own brief when you are ready.
              </h2>
              <p className="mt-4 max-w-2xl leading-7 text-orange-50/90">
                The recorded demo is intentionally credential-free. A real run
                uses your configured model provider and clearly marks observed
                evidence, estimates, and assumptions.
              </p>
            </div>
            <Button
              asChild
              size="lg"
              className="bg-white text-orange-800 hover:bg-orange-50"
            >
              <a
                href="https://github.com/CheungkiCheung/opensku#quick-start"
                target="_blank"
                rel="noreferrer"
              >
                Open Quick Start
                <ArrowRight />
              </a>
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}
