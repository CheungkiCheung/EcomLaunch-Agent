import {
  ArrowRight,
  CheckCircle2,
  CirclePause,
  Database,
  ExternalLink,
  FileCheck2,
  FileText,
  Github,
  KeyRound,
  Languages,
  PlayCircle,
  Radio,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import {
  chineseScenarioTranslations,
  demoSharedCopy,
  type DemoLanguage,
  type DemoScenario,
  type ScenarioTranslation,
  type VerificationLoopContent,
} from "./demo-locales";
import { GuidedWalkthrough } from "./guided-walkthrough";
import { LaunchVerificationLoop } from "./launch-verification-loop";

type Participant = {
  id: string;
  imageId: string;
  name: string;
  status: "Done" | "Not used";
  activity: string;
  left: number;
  top: number;
  color: string;
};

type ScenarioConfig = {
  label: string;
  shortLabel: string;
  navDescription: string;
  eyebrow: string;
  title: string;
  description: string;
  decision: string;
  briefTitle: string;
  briefFields: Array<{ label: string; value: string }>;
  notice: string;
  warRoomEyebrow: string;
  warRoomTitle: string;
  replayLabel: string;
  replayDescription: string;
  participants: Participant[];
  pipelineTitle: string;
  pipeline: Array<{ label: string; detail: string; kind: string }>;
  stats: Array<{ value: string; label: string }>;
  verificationEyebrow: string;
  verificationTitle: string;
  verificationDescription: string;
  verificationSteps: Array<{
    label: string;
    title: string;
    detail: string;
    status: "passed" | "blocked" | "revised";
  }>;
  verificationLoop?: VerificationLoopContent;
  deliverablesTitle: string;
  deliverablesDescription: string;
  deliverables: Array<{
    title: string;
    description: string;
    href: string;
    label: string;
  }>;
  alternateLabel: string;
  alternateHref: string;
};

const scenarios: Record<DemoScenario, ScenarioConfig> = {
  launch: {
    label: "Launch Validation",
    shortLabel: "Launch",
    navDescription: "Brief → specialist team → verified decision pack",
    eyebrow: "ENGLISH SAMPLE · NO API KEY",
    title: "Turn one product brief into a decision-ready launch pack.",
    description:
      "This deterministic walkthrough validates a hypothetical compact travel coffee mug for the US market. Follow the real three-specialist topology, inspect the preflight gate, and open the resulting sample files.",
    decision: "VALIDATE",
    briefTitle: "Compact travel coffee mug",
    briefFields: [
      { label: "Market", value: "United States" },
      { label: "Audience", value: "Commuters and frequent travelers" },
      { label: "Price test", value: "$24–$34 hypothesis" },
      { label: "Constraint", value: "Leak-resistant and under 350 g" },
    ],
    notice:
      "The market findings are deterministic fixtures, not current research. The agent topology matches the active Ultra configuration; verification is shown as a system gate, not as an extra agent.",
    warRoomEyebrow: "01 · Multi-agent runtime",
    warRoomTitle: "Four active agents. One deterministic gate.",
    replayLabel: "Replay complete",
    replayDescription: "Compact travel mug validation",
    participants: [
      {
        id: "ecom-launch",
        imageId: "ecom-launch",
        name: "Launch Director",
        status: "Done",
        activity: "Decision pack assembled",
        left: 50,
        top: 43,
        color: "#f2b35f",
      },
      {
        id: "market-voc-researcher",
        imageId: "market-voc-researcher",
        name: "Market Researcher",
        status: "Done",
        activity: "Sample signal map prepared",
        left: 15,
        top: 37,
        color: "#e98b63",
      },
      {
        id: "offer-architect",
        imageId: "offer-architect",
        name: "Offer Architect",
        status: "Done",
        activity: "Positioning hypothesis drafted",
        left: 40,
        top: 24,
        color: "#d87855",
      },
      {
        id: "asset-studio",
        imageId: "asset-studio",
        name: "Asset Studio",
        status: "Done",
        activity: "Listing and content assets created",
        left: 31,
        top: 75,
        color: "#ca6d67",
      },
      {
        id: "data-inspector",
        imageId: "data-inspector",
        name: "Growth Analyst",
        status: "Not used",
        activity: "No store dataset in this brief",
        left: 73,
        top: 79,
        color: "#78a99d",
      },
    ],
    pipelineTitle: "Dependency order",
    pipeline: [
      {
        label: "Research",
        detail: "Market signals and customer language",
        kind: "AGENT",
      },
      {
        label: "Offer",
        detail: "Positioning, pricing, and validation hypotheses",
        kind: "AGENT",
      },
      {
        label: "Assets",
        detail: "Listing copy, hooks, and scripts",
        kind: "AGENT",
      },
      {
        label: "Preflight",
        detail: "Seven-file, evidence, JSON/CSV, and claim checks",
        kind: "SYSTEM",
      },
    ],
    stats: [
      { value: "3", label: "specialists" },
      { value: "7/7", label: "required files" },
      { value: "0", label: "live API calls" },
    ],
    verificationEyebrow: "02 · Verification loop",
    verificationTitle: "The model cannot approve its own delivery.",
    verificationDescription:
      "A deterministic preflight blocks incomplete files, malformed data, weak evidence boundaries, and unsupported physical-product claims. Only the failed artifacts are revised before the pack is checked again.",
    verificationSteps: [
      {
        label: "Generate",
        title: "Seven-file pack assembled",
        detail:
          "The lead agent collects the specialist outputs into the delivery contract.",
        status: "passed",
      },
      {
        label: "Preflight",
        title: "Fixture defects blocked",
        detail:
          "A missing evidence URL and an unsupported leak-proof claim fail the gate.",
        status: "blocked",
      },
      {
        label: "Revise",
        title: "Two artifacts edited",
        detail:
          "The failure observation opens only bounded file-edit tools for a minimal revision.",
        status: "revised",
      },
      {
        label: "Recheck",
        title: "7/7 contract passed",
        detail:
          "Files, evidence labels, URLs, structured data, and claim boundaries pass.",
        status: "passed",
      },
    ],
    verificationLoop: {
      title: "Bounded agent-environment verification loop",
      budget: "2 / 5 iterations used",
      firstRound: {
        label: "Loop 01 / 05",
        actionLabel: "Agent action",
        action: "present_files(7 artifacts)",
        observationLabel: "Environment observation",
        result: "Blocked · 2 violations",
        violations: [
          "evidence-ledger.json · observed_public entry missing source_url",
          "listing-pack.md · unsupported ‘leak-proof’ product claim",
        ],
      },
      decision: {
        label: "Agent decision",
        title: "Minimal repair selected from Observation",
        basis:
          "The failure list determines the next files and tools; the other five artifacts stay untouched.",
        filesLabel: "Files selected · 2 / 7",
        files: ["evidence-ledger.json", "listing-pack.md"],
        toolsLabel: "Tools unlocked",
        tools: ["str_replace", "write_file"],
        unchanged: "Unchanged artifacts: 5 · full-pack regeneration skipped",
      },
      rerun: {
        label: "Next action chosen from environment feedback",
        action:
          "Repair the two failed artifacts, then call present_files again.",
      },
      secondRound: {
        label: "Loop 02 / 05",
        actionLabel: "Agent action",
        action: "present_files(7 artifacts)",
        observationLabel: "New environment observation",
        result: "Passed · 7 / 7",
        checks: [
          "Required files 7/7",
          "Missing source URLs 0",
          "Blocked claims 0",
          "Invalid JSON/CSV 0",
        ],
      },
      stop: {
        label: "Stop condition",
        title: "Success criteria met",
        reason:
          "The environment returned a clean delivery contract, so the agent stops instead of spending the remaining loop budget.",
        metrics: [
          "Iterations used 2/5",
          "Revision scope 2/7 files",
          "Run Budget not triggered",
          "Duplicate-tool guard not triggered",
        ],
      },
    },
    deliverablesTitle: "Not just a chat answer.",
    deliverablesDescription:
      "Open each file to inspect the decision structure, evidence boundaries, editable launch assets, and explicit stop conditions.",
    deliverables: [
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
    ],
    alternateLabel: "Show Growth Analyst",
    alternateHref: "/demo?scenario=growth",
  },
  growth: {
    label: "Growth Experiment",
    shortLabel: "Growth",
    navDescription: "CSV/XLSX → read-only analysis → ship/extend/stop",
    eyebrow: "DETERMINISTIC ANALYSIS · NO API KEY",
    title: "Turn three business files into an experiment decision.",
    description:
      "This recorded Growth Analyst scenario joins visitor, assignment, and order data; runs a deterministic two-proportion test and SRM check; and writes the decision into a bounded memory snapshot.",
    decision: "SHIP",
    briefTitle: "Checkout social-proof experiment",
    briefFields: [
      { label: "Inputs", value: "Visitors + assignments + orders" },
      { label: "Population", value: "2,380 assigned visitors" },
      { label: "Primary metric", value: "Purchase conversion" },
      { label: "Question", value: "Should treatment ship?" },
    ],
    notice:
      "All rows and metrics are deterministic fixtures. No uploaded user data is included, no model is called, and the SQL/statistical results are reproducible from the displayed sample counts.",
    warRoomEyebrow: "01 · Bounded analysis runtime",
    warRoomTitle: "One analyst. Four deterministic stages.",
    replayLabel: "Analysis complete",
    replayDescription: "Checkout experiment decision",
    participants: [
      {
        id: "data-inspector",
        imageId: "data-inspector",
        name: "Growth Analyst",
        status: "Done",
        activity: "SHIP recommendation recorded",
        left: 49,
        top: 48,
        color: "#5d9d90",
      },
      {
        id: "ecom-launch",
        imageId: "ecom-launch",
        name: "Launch Director",
        status: "Not used",
        activity: "No launch brief in this scenario",
        left: 24,
        top: 70,
        color: "#c5a06e",
      },
    ],
    pipelineTitle: "Deterministic stages",
    pipeline: [
      {
        label: "Inspect",
        detail: "CSV/XLSX type, schema, and row checks",
        kind: "TOOL",
      },
      {
        label: "Join",
        detail: "Read-only DuckDB query across three registered files",
        kind: "SQL",
      },
      {
        label: "Test",
        detail: "Two-proportion z-test, confidence interval, and SRM",
        kind: "STATS",
      },
      {
        label: "Remember",
        detail: "Decision and metric context written to business memory",
        kind: "MEMORY",
      },
    ],
    stats: [
      { value: "+31.4%", label: "relative lift" },
      { value: "0.0346", label: "p-value" },
      { value: "0.682", label: "SRM p-value" },
    ],
    verificationEyebrow: "02 · Deterministic analysis",
    verificationTitle: "The recommendation is backed by inspectable math.",
    verificationDescription:
      "The recorded fixture uses 96/1,200 control conversions and 124/1,180 treatment conversions. The result is significant at the predeclared 5% threshold, the allocation passes the SRM check, and the absolute-lift confidence interval stays above zero.",
    verificationSteps: [
      {
        label: "Inspect",
        title: "Three files registered",
        detail:
          "Allowed tabular formats and required join keys pass schema inspection.",
        status: "passed",
      },
      {
        label: "Join",
        title: "2,380 visitors reconciled",
        detail:
          "A bounded SELECT joins assignments, visitors, and orders without external access.",
        status: "passed",
      },
      {
        label: "Test",
        title: "+2.51 pp absolute lift",
        detail: "p = 0.0346; 95% CI = +0.18 to +4.84 pp; SRM p = 0.682.",
        status: "passed",
      },
      {
        label: "Decide",
        title: "SHIP with monitoring",
        detail:
          "Roll out gradually and monitor refund rate, AOV, and the conversion lift.",
        status: "revised",
      },
    ],
    deliverablesTitle: "A decision you can audit.",
    deliverablesDescription:
      "Inspect the recommendation, statistical calculation, cohort snapshot, and the bounded memory entry carried into the next session.",
    deliverables: [
      {
        title: "Growth decision",
        description:
          "A Ship / Extend / Stop recommendation with thresholds and rollout guardrails.",
        href: "/demo/opensku-growth-experiment/growth-decision.md",
        label: "DECISION",
      },
      {
        title: "Experiment analysis",
        description:
          "Joined counts, conversion rates, z-test, confidence interval, and SRM details.",
        href: "/demo/opensku-growth-experiment/experiment-analysis.md",
        label: "EXPERIMENT",
      },
      {
        title: "Cohort retention",
        description:
          "A compact CSV fixture showing acquisition cohorts and week-four retention.",
        href: "/demo/opensku-growth-experiment/cohort-retention.csv",
        label: "COHORT",
      },
      {
        title: "Memory snapshot",
        description:
          "The metric context and experiment conclusion retained for a later conversation.",
        href: "/demo/opensku-growth-experiment/memory-snapshot.md",
        label: "MEMORY",
      },
    ],
    alternateLabel: "Show Launch Validation",
    alternateHref: "/demo?scenario=launch",
  },
};

const themes: Record<
  DemoScenario,
  {
    badge: string;
    primaryButton: string;
    glowOne: string;
    glowTwo: string;
    eyebrow: string;
    decision: string;
    verificationBackground: string;
    finalGradient: string;
  }
> = {
  launch: {
    badge: "border-orange-300/80 bg-orange-100 text-orange-900",
    primaryButton: "bg-orange-600 text-white hover:bg-orange-700",
    glowOne: "bg-orange-300/35",
    glowTwo: "bg-amber-200/60",
    eyebrow: "text-orange-700",
    decision: "bg-amber-100 text-amber-900",
    verificationBackground: "bg-[#fff8ed]",
    finalGradient: "from-orange-600 to-amber-500",
  },
  growth: {
    badge: "border-teal-300/80 bg-teal-100 text-teal-900",
    primaryButton: "bg-teal-700 text-white hover:bg-teal-800",
    glowOne: "bg-teal-300/35",
    glowTwo: "bg-emerald-200/55",
    eyebrow: "text-teal-700",
    decision: "bg-emerald-100 text-emerald-900",
    verificationBackground: "bg-[#eff9f4]",
    finalGradient: "from-teal-700 to-emerald-500",
  },
};

function ActorSprite({
  actor,
  statusText,
}: {
  actor: Participant;
  statusText: string;
}) {
  return (
    <div
      className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
      style={{ left: `${actor.left}%`, top: `${actor.top}%` }}
    >
      <div
        role="img"
        aria-label={`${actor.name}: ${statusText}`}
        className={`mx-auto h-[54px] w-9 bg-left-top bg-no-repeat drop-shadow-[0_5px_4px_rgba(74,45,26,0.35)] ${
          actor.status === "Not used" ? "opacity-55 grayscale" : ""
        }`}
        style={{
          backgroundImage: `url(/war-room-original/characters/${actor.imageId}.png)`,
          backgroundSize: "144px 54px",
          imageRendering: "pixelated",
        }}
      />
      <div className="mt-1 hidden rounded-full border border-white/75 bg-stone-950/75 px-2 py-0.5 text-[9px] font-semibold whitespace-nowrap text-white shadow-sm backdrop-blur-sm sm:block">
        {actor.name}
      </div>
    </div>
  );
}

function statusClasses(status: "passed" | "blocked" | "revised") {
  if (status === "blocked") {
    return "border-rose-200 bg-rose-50 text-rose-800";
  }
  if (status === "revised") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-800";
}

type DemoPageProps = {
  searchParams?: Promise<{
    scenario?: string | string[];
    lang?: string | string[];
  }>;
};

function singleSearchParam(value?: string | string[]) {
  return Array.isArray(value) ? value[0] : value;
}

function localizeScenario(
  base: ScenarioConfig,
  translation: ScenarioTranslation,
): ScenarioConfig {
  return {
    ...base,
    ...translation,
    participants: base.participants.map((participant) => ({
      ...participant,
      ...(translation.participants[participant.id] ?? {}),
    })),
    verificationSteps: base.verificationSteps.map((step, index) => ({
      ...step,
      ...translation.verificationSteps[index],
    })),
    alternateHref: base.alternateHref,
  };
}

export async function generateMetadata({
  searchParams,
}: DemoPageProps): Promise<Metadata> {
  const params = await searchParams;
  const language: DemoLanguage =
    singleSearchParam(params?.lang) === "zh" ? "zh" : "en";
  const copy = demoSharedCopy[language];
  return {
    title: copy.metadataTitle,
    description: copy.metadataDescription,
  };
}

export default async function DemoPage({ searchParams }: DemoPageProps) {
  const params = await searchParams;
  const requestedScenario = singleSearchParam(params?.scenario);
  const scenario: DemoScenario =
    requestedScenario === "growth" ? "growth" : "launch";
  const language: DemoLanguage =
    singleSearchParam(params?.lang) === "zh" ? "zh" : "en";
  const copy = demoSharedCopy[language];
  const content =
    language === "zh"
      ? localizeScenario(
          scenarios[scenario],
          chineseScenarioTranslations[scenario],
        )
      : scenarios[scenario];
  const theme = themes[scenario];
  const completedParticipants = content.participants.filter(
    (participant) => participant.status === "Done",
  ).length;

  return (
    <main
      lang={language === "zh" ? "zh-CN" : "en"}
      className="min-h-screen bg-[#f3eadc] text-stone-900"
    >
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
                {copy.brandSubtitle}
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
              <a href="#deliverables">{copy.sampleOutputs}</a>
            </Button>
            <div
              role="group"
              aria-label={copy.languageLabel}
              className="flex items-center rounded-lg border border-stone-900/10 bg-white/70 p-0.5"
            >
              <Languages className="mx-1 hidden size-3.5 text-stone-500 sm:block" />
              <Link
                href={`/demo?scenario=${scenario}&lang=en`}
                aria-current={language === "en" ? "page" : undefined}
                data-testid="lang-en"
                className={`rounded-md px-2 py-1 text-xs font-bold transition ${
                  language === "en"
                    ? "bg-stone-900 text-white"
                    : "text-stone-500 hover:text-stone-900"
                }`}
              >
                {copy.languageEnglish}
              </Link>
              <Link
                href={`/demo?scenario=${scenario}&lang=zh`}
                aria-current={language === "zh" ? "page" : undefined}
                data-testid="lang-zh"
                className={`rounded-md px-2 py-1 text-xs font-bold transition ${
                  language === "zh"
                    ? "bg-stone-900 text-white"
                    : "text-stone-500 hover:text-stone-900"
                }`}
              >
                {copy.languageChinese}
              </Link>
            </div>
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

      <nav
        aria-label={copy.scenariosAriaLabel}
        className="border-b border-stone-900/10 bg-white/55"
      >
        <div className="mx-auto grid max-w-3xl gap-2 px-5 py-3 sm:grid-cols-2 lg:px-8">
          {(
            Object.entries(scenarios) as Array<[DemoScenario, ScenarioConfig]>
          ).map(([id, option]) => {
            const selected = id === scenario;
            const localizedOption =
              language === "zh" ? chineseScenarioTranslations[id] : option;
            return (
              <Link
                key={id}
                href={`/demo?scenario=${id}&lang=${language}`}
                aria-current={selected ? "page" : undefined}
                data-testid={`scenario-${id}`}
                className={`rounded-2xl border px-4 py-3 transition ${
                  selected
                    ? "border-stone-950 bg-stone-950 text-white shadow-lg"
                    : "border-stone-900/10 bg-white/70 text-stone-700 hover:border-stone-400 hover:bg-white"
                }`}
              >
                <span className="block text-sm font-black">
                  {localizedOption.label}
                </span>
                <span
                  className={`mt-0.5 block text-xs ${
                    selected ? "text-stone-300" : "text-stone-500"
                  }`}
                >
                  {localizedOption.navDescription}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>

      <GuidedWalkthrough scenario={scenario} language={language} />

      <section
        id="demo-brief"
        className="relative scroll-mt-32 overflow-hidden border-b border-stone-900/10"
      >
        <div
          className={`absolute -top-40 right-[-10%] size-[520px] rounded-full ${theme.glowOne} blur-3xl`}
        />
        <div
          className={`absolute bottom-[-55%] left-[-8%] size-[520px] rounded-full ${theme.glowTwo} blur-3xl`}
        />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-5 py-16 lg:grid-cols-[1.25fr_0.75fr] lg:px-8 lg:py-24">
          <div>
            <Badge className={theme.badge} variant="outline">
              <PlayCircle />
              {content.eyebrow}
            </Badge>
            <h1 className="mt-6 max-w-4xl text-4xl leading-[1.05] font-black tracking-[-0.04em] text-stone-950 sm:text-6xl">
              {content.title}
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-stone-600">
              {content.description}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg" className={theme.primaryButton}>
                <a href="#war-room">
                  {copy.exploreRuntime}
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
                  href={content.deliverables[0]?.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  {copy.readDecision}
                  <ExternalLink />
                </a>
              </Button>
            </div>
          </div>

          <aside className="rounded-[2rem] border border-white/80 bg-white/65 p-6 shadow-[0_24px_70px_rgba(94,62,34,0.13)] backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold tracking-[0.18em] text-stone-500 uppercase">
                {copy.sampleBrief}
              </span>
              <Badge className={theme.decision}>{content.decision}</Badge>
            </div>
            <h2 className="mt-5 text-2xl font-bold tracking-tight">
              {content.briefTitle}
            </h2>
            <dl className="mt-6 grid gap-4 text-sm">
              {content.briefFields.map((field) => (
                <div
                  key={field.label}
                  className="grid grid-cols-[92px_1fr] gap-3 border-t border-stone-900/10 pt-4"
                >
                  <dt className="font-medium text-stone-500">{field.label}</dt>
                  <dd className="font-semibold">{field.value}</dd>
                </div>
              ))}
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
            <p className="font-bold text-amber-950">{copy.recordedTitle}</p>
            <p className="mt-1 text-sm leading-6 text-amber-900/75">
              {content.notice}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-bold text-amber-900">
            <KeyRound className="size-4" />
            {copy.zeroKeys}
          </div>
        </div>
      </section>

      <section
        id="war-room"
        className="mx-auto max-w-7xl scroll-mt-32 px-5 py-12 lg:px-8 lg:py-16"
      >
        <div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <span
              className={`text-xs font-black tracking-[0.2em] uppercase ${theme.eyebrow}`}
            >
              {content.warRoomEyebrow}
            </span>
            <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
              {content.warRoomTitle}
            </h2>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            {content.stats.map((stat) => (
              <span
                key={stat.label}
                className="rounded-full bg-white/75 px-3 py-1.5 text-stone-700 shadow-sm"
              >
                <strong className="text-stone-950">{stat.value}</strong>{" "}
                {stat.label}
              </span>
            ))}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.55fr)]">
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
            {content.participants.map((actor) => (
              <ActorSprite
                key={actor.id}
                actor={actor}
                statusText={actor.status === "Done" ? copy.done : copy.notUsed}
              />
            ))}
            <div className="absolute top-3 left-3 rounded-xl border border-white/60 bg-stone-950/70 px-3 py-2 text-white shadow-lg backdrop-blur-md sm:top-5 sm:left-5">
              <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.16em] text-amber-300 uppercase">
                <Sparkles className="size-3" />
                {content.replayLabel}
              </div>
              <p className="mt-1 hidden text-xs text-white/75 sm:block">
                {content.replayDescription}
              </p>
            </div>
            <div className="absolute right-4 bottom-4 left-4 hidden grid-cols-4 gap-2 md:grid">
              {content.pipeline.map((stage, index) => (
                <div
                  key={stage.label}
                  className="rounded-xl border border-white/20 bg-stone-950/72 p-2.5 text-white shadow-lg backdrop-blur-md"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-black">
                      {index + 1}. {stage.label}
                    </span>
                    <span className="text-[8px] font-black tracking-[0.12em] text-amber-300">
                      {stage.kind}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[9px] leading-3 text-white/65">
                    {stage.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div
              data-testid="demo-agent-status"
              className="rounded-[1.75rem] border border-white/80 bg-white/65 p-4 shadow-[0_18px_55px_rgba(82,54,31,0.12)] backdrop-blur-xl"
            >
              <div className="flex items-center justify-between px-2 py-2">
                <div>
                  <p className="text-xs font-black tracking-[0.18em] text-stone-500 uppercase">
                    {copy.agentStatus}
                  </p>
                  <p className="mt-1 text-sm text-stone-500">
                    {copy.activeInScenario(completedParticipants)}
                  </p>
                </div>
                <ShieldCheck className="size-6 text-emerald-700" />
              </div>
              <div className="mt-2 space-y-2">
                {content.participants.map((actor) => {
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
                            {complete ? copy.done : copy.notUsed}
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

            <div
              data-testid="deterministic-pipeline"
              className="rounded-[1.75rem] border border-stone-900/10 bg-stone-950 p-5 text-white shadow-[0_18px_55px_rgba(82,54,31,0.16)]"
            >
              <div className="flex items-center gap-2">
                <Workflow className="size-4 text-amber-300" />
                <p className="text-xs font-black tracking-[0.16em] text-amber-300 uppercase">
                  {content.pipelineTitle}
                </p>
              </div>
              <div className="mt-4 space-y-3">
                {content.pipeline.map((stage, index) => (
                  <div key={stage.label} className="flex gap-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-white/10 text-[10px] font-black">
                      {index + 1}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-bold">{stage.label}</p>
                        <span className="text-[8px] font-black tracking-[0.12em] text-stone-500">
                          {stage.kind}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs leading-5 text-stone-400">
                        {stage.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        id="verification"
        data-testid="demo-verification"
        className={`scroll-mt-32 border-y border-stone-900/10 ${theme.verificationBackground}`}
      >
        <div className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-24">
          <div
            className={`grid gap-10 lg:items-start ${
              scenario === "launch"
                ? "lg:grid-cols-[0.5fr_1.5fr]"
                : "lg:grid-cols-[0.72fr_1.28fr]"
            }`}
          >
            <div>
              <span
                className={`text-xs font-black tracking-[0.2em] uppercase ${theme.eyebrow}`}
              >
                {content.verificationEyebrow}
              </span>
              <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">
                {content.verificationTitle}
              </h2>
              <p className="mt-5 max-w-lg leading-7 text-stone-600">
                {content.verificationDescription}
              </p>
            </div>

            {scenario === "launch" && content.verificationLoop ? (
              <LaunchVerificationLoop content={content.verificationLoop} />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {content.verificationSteps.map((step, index) => (
                  <article
                    key={step.label}
                    className="rounded-2xl border border-stone-900/10 bg-white/80 p-5 shadow-sm"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-black tracking-[0.14em] text-stone-400 uppercase">
                        {String(index + 1).padStart(2, "0")} · {step.label}
                      </span>
                      <Badge
                        variant="outline"
                        className={statusClasses(step.status)}
                      >
                        {copy.status[step.status]}
                      </Badge>
                    </div>
                    <h3 className="mt-6 text-lg font-bold">{step.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-stone-500">
                      {step.detail}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <section
        id="deliverables"
        className="scroll-mt-32 bg-stone-950 text-white"
      >
        <div className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr]">
            <div>
              <span className="text-xs font-black tracking-[0.2em] text-amber-300 uppercase">
                {copy.deliverablesEyebrow}
              </span>
              <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">
                {content.deliverablesTitle}
              </h2>
              <p className="mt-5 max-w-md leading-7 text-stone-300">
                {content.deliverablesDescription}
              </p>
              <div className="mt-8 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-3xl font-black text-amber-300">
                    {content.deliverables.length}
                  </p>
                  <p className="mt-1 text-stone-400">{copy.inspectableFiles}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-3xl font-black text-amber-300">0</p>
                  <p className="mt-1 text-stone-400">{copy.liveApiCalls}</p>
                </div>
              </div>
            </div>

            <div
              data-testid="demo-deliverables"
              className="grid gap-3 sm:grid-cols-2"
            >
              {content.deliverables.map((deliverable) => (
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
                    {copy.openFile}
                    <ExternalLink className="size-3.5" />
                  </div>
                </a>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-24">
        <div
          className={`rounded-[2rem] bg-gradient-to-br ${theme.finalGradient} p-8 text-white shadow-[0_28px_80px_rgba(82,54,31,0.22)] sm:p-12`}
        >
          <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <p className="text-xs font-black tracking-[0.2em] text-white/75 uppercase">
                {copy.continueEyebrow}
              </p>
              <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
                {copy.continueTitle}
              </h2>
              <p className="mt-4 max-w-2xl leading-7 text-white/85">
                {copy.continueDescription}
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-white/30 bg-white/10 text-white hover:bg-white/20 hover:text-white"
              >
                <Link
                  href={`/demo?scenario=${
                    scenario === "launch" ? "growth" : "launch"
                  }&lang=${language}`}
                >
                  {content.alternateLabel}
                  <ArrowRight />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                className="bg-white text-stone-900 hover:bg-stone-100"
              >
                <a
                  href="https://github.com/CheungkiCheung/opensku#quick-start"
                  target="_blank"
                  rel="noreferrer"
                >
                  <FileCheck2 />
                  {copy.quickStart}
                </a>
              </Button>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-stone-900/10 bg-white/45">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-8 text-sm text-stone-500 sm:flex-row sm:items-center sm:justify-between lg:px-8">
          <div className="flex items-center gap-2">
            {scenario === "growth" ? (
              <Database className="size-4" />
            ) : (
              <Workflow className="size-4" />
            )}
            {copy.footerRecorded}
          </div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4" />
            {copy.footerClaims}
          </div>
        </div>
      </footer>
    </main>
  );
}
