"use client";

import type { Message } from "@langchain/langgraph-sdk";
import {
  ArrowRightIcon,
  CheckCircle2Icon,
  ChevronRightIcon,
  CircleAlertIcon,
  ClipboardCheckIcon,
  ExternalLinkIcon,
  FileCheck2Icon,
  FileClockIcon,
  FlaskConicalIcon,
  Loader2Icon,
  PlusIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useArtifacts } from "@/components/workspace/artifacts";
import { useArtifactContent } from "@/core/artifacts/hooks";
import { LAUNCH_PACK_FILENAMES } from "@/core/artifacts/launch-pack";
import { useI18n } from "@/core/i18n/hooks";
import type { Translations } from "@/core/i18n/locales/types";
import {
  buildDecisionWorkspaceModel,
  buildGrowthAnalystHandoff,
  formatValidationResultMessage,
  type EvidenceState,
  type LaunchDecisionWorkspaceModel,
  type LaunchExperiment,
  type ValidationOutcome,
  type ValidationResult,
} from "@/core/launch-validation/decision";
import { getFileName } from "@/core/utils/files";
import { cn } from "@/lib/utils";

type LaunchDecisionWorkspaceProps = {
  threadId: string;
  messages: Message[];
  isStreaming: boolean;
  onRecordValidationResult: (
    message: PromptInputMessage,
  ) => void | Promise<void>;
  onOpenGrowthAnalyst: (handoff: string) => void;
  onReturnToChat: () => void;
};

type ValidationDraft = Omit<ValidationResult, "messageIndex">;

const EMPTY_DRAFT: ValidationDraft = {
  experiment: "",
  date: "",
  sampleDefinition: "",
  observation: "",
  outcome: "inconclusive",
};

function today() {
  const date = new Date();
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function findArtifact(artifacts: string[], filename: string) {
  return artifacts.find((filepath) => getFileName(filepath) === filename) ?? "";
}

function displayValue(value: string | undefined, fallback: string) {
  return value?.trim() ? value : fallback;
}

function statusTone(state: EvidenceState) {
  if (state === "supported") {
    return "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  }
  if (state === "conflicting") {
    return "border-rose-600/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  }
  if (state === "partial") {
    return "border-amber-600/30 bg-amber-500/10 text-amber-800 dark:text-amber-300";
  }
  return "border-border bg-muted text-muted-foreground";
}

function outcomeTone(outcome: ValidationOutcome) {
  if (outcome === "met") {
    return "text-emerald-700 dark:text-emerald-300";
  }
  if (outcome === "not_met") {
    return "text-rose-700 dark:text-rose-300";
  }
  if (outcome === "partial") {
    return "text-amber-700 dark:text-amber-300";
  }
  return "text-muted-foreground";
}

function SummaryItem({
  label,
  value,
  danger,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className="border-border min-w-0 border-l-2 pl-3">
      <div className="text-muted-foreground text-xs font-medium">{label}</div>
      <div
        className={cn(
          "mt-1 text-sm leading-5 font-medium break-words",
          danger && "text-rose-700 dark:text-rose-300",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function DecisionOverview({
  model,
  copy,
}: {
  model: LaunchDecisionWorkspaceModel;
  copy: Translations["launchDecision"];
}) {
  const spec = model.currentSpec!;
  const initial = model.initialSpec!;
  return (
    <div className="space-y-8">
      <section aria-labelledby="decision-context-heading">
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h2 id="decision-context-heading" className="text-sm font-semibold">
              {copy.decisionContext}
            </h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground text-xs">
                  {copy.audience}
                </dt>
                <dd className="mt-1 text-sm leading-6">
                  {spec.audience || copy.notDefined}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">
                  {copy.validationGoal}
                </dt>
                <dd className="mt-1 text-sm leading-6">
                  {spec.validationGoal || copy.notDefined}
                </dd>
              </div>
            </dl>
          </div>

          <div className="border-border border-t pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6">
            <h2 className="text-sm font-semibold">{copy.decisionDifference}</h2>
            <div className="mt-4 flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-muted-foreground text-xs">
                  {copy.initial}
                </div>
                <div className="mt-1 text-sm font-medium">
                  {copy.decisions[initial.decision]}
                </div>
              </div>
              <ArrowRightIcon className="text-muted-foreground mt-4 size-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="text-muted-foreground text-xs">
                  {copy.current}
                </div>
                <div className="mt-1 text-sm font-medium">
                  {copy.decisions[spec.decision]}
                </div>
              </div>
            </div>
            <div className="border-border mt-4 border-l-2 pl-3 text-sm leading-6">
              {model.pendingReassessment ? (
                <span className="text-amber-700 dark:text-amber-300">
                  {copy.pendingReassessment}
                </span>
              ) : model.decisionChanged ? (
                spec.decisionRationale || copy.changedWithoutRationale
              ) : (
                copy.noDecisionChange
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="border-border border-t pt-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">{copy.recordedResults}</h2>
          <Badge variant="outline">{model.validationResults.length}</Badge>
        </div>
        {model.validationResults.length === 0 ? (
          <p className="text-muted-foreground mt-3 text-sm">
            {copy.noRecordedResults}
          </p>
        ) : (
          <div className="mt-4 divide-y">
            {[...model.validationResults].reverse().map((result, index) => (
              <div
                className="grid gap-2 py-4 first:pt-0 sm:grid-cols-[150px_1fr_auto]"
                key={`${result.messageIndex}-${index}`}
              >
                <div>
                  <div className="text-sm font-medium">{result.experiment}</div>
                  <div className="text-muted-foreground mt-1 text-xs">
                    {result.date || copy.dateUnknown}
                  </div>
                </div>
                <div className="text-muted-foreground text-sm leading-5">
                  <div>{result.observation}</div>
                  {result.sampleDefinition && (
                    <div className="mt-1 text-xs">
                      {copy.sampleDefinition}: {result.sampleDefinition}
                    </div>
                  )}
                </div>
                <div
                  className={cn(
                    "text-xs font-medium sm:text-right",
                    outcomeTone(result.outcome),
                  )}
                >
                  {copy.outcomes[result.outcome]}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ExperimentsView({
  experiments,
  copy,
  onRecord,
}: {
  experiments: LaunchExperiment[];
  copy: Translations["launchDecision"];
  onRecord: (experiment: string) => void;
}) {
  const visibleExperiments = experiments.length
    ? experiments
    : copy.experimentTemplates.map((template, index) => ({
        day: String(index + 1),
        action: template.name,
        evidenceToCollect: template.evidence,
        successCriterion: template.success,
        stopCondition: template.stop,
      }));
  return (
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">{copy.experimentPlan}</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              {experiments.length
                ? copy.experimentPlanDescription
                : copy.templateFallbackDescription}
            </p>
          </div>
        </div>
        <div className="mt-5 divide-y border-y">
          {visibleExperiments.map((experiment, index) => (
            <div
              className="grid gap-4 py-5 lg:grid-cols-[64px_minmax(180px,1.1fr)_minmax(180px,1fr)_auto]"
              key={`${experiment.day}-${experiment.action}-${index}`}
            >
              <div className="flex size-11 items-center justify-center rounded-md border font-mono text-xs font-semibold">
                D{experiment.day}
              </div>
              <div>
                <div className="text-sm leading-5 font-semibold">
                  {experiment.action}
                </div>
                <div className="text-muted-foreground mt-2 text-xs leading-5">
                  <span className="text-foreground font-medium">
                    {copy.collect}:
                  </span>{" "}
                  {experiment.evidenceToCollect || copy.notDefined}
                </div>
              </div>
              <div className="space-y-2 text-xs leading-5">
                <div>
                  <span className="font-medium text-emerald-700 dark:text-emerald-300">
                    {copy.successCriterion}:
                  </span>{" "}
                  {experiment.successCriterion || copy.notDefined}
                </div>
                <div>
                  <span className="font-medium text-rose-700 dark:text-rose-300">
                    {copy.stopCondition}:
                  </span>{" "}
                  {experiment.stopCondition || copy.notDefined}
                </div>
              </div>
              <Button
                className="self-start"
                size="sm"
                variant="outline"
                onClick={() => onRecord(experiment.action)}
              >
                <PlusIcon />
                {copy.recordResult}
              </Button>
            </div>
          ))}
        </div>
      </section>

      <section className="border-border border-t pt-6">
        <h2 className="text-sm font-semibold">
          {copy.experimentTemplatesTitle}
        </h2>
        <div className="bg-border mt-4 grid gap-px overflow-hidden rounded-md border sm:grid-cols-2 xl:grid-cols-4">
          {copy.experimentTemplates.map((template) => (
            <button
              className="bg-background hover:bg-muted/50 min-h-28 p-4 text-left transition-colors"
              key={template.name}
              onClick={() => onRecord(template.name)}
              type="button"
            >
              <div className="flex items-center justify-between gap-2">
                <FlaskConicalIcon className="text-muted-foreground size-4" />
                <ChevronRightIcon className="text-muted-foreground size-4" />
              </div>
              <div className="mt-3 text-sm font-semibold">{template.name}</div>
              <div className="text-muted-foreground mt-1 text-xs leading-5">
                {template.evidence}
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function EvidenceView({
  model,
  copy,
}: {
  model: LaunchDecisionWorkspaceModel;
  copy: Translations["launchDecision"];
}) {
  const hypotheses = model.currentSpec?.hypotheses ?? [];
  return (
    <div className="space-y-8">
      <section>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">{copy.keyHypotheses}</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              {copy.hypothesisLinkNotice}
            </p>
          </div>
          <Badge variant="outline">{hypotheses.length}</Badge>
        </div>
        {hypotheses.length === 0 ? (
          <p className="text-muted-foreground mt-4 text-sm">
            {copy.noHypotheses}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto border-y">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="text-muted-foreground bg-muted/40 text-xs">
                <tr>
                  <th className="px-3 py-3 font-medium">{copy.hypothesis}</th>
                  <th className="px-3 py-3 font-medium">{copy.status}</th>
                  <th className="px-3 py-3 font-medium">{copy.evidence}</th>
                  <th className="px-3 py-3 font-medium">
                    {copy.decisionImpact}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {hypotheses.map((hypothesis) => (
                  <tr key={hypothesis}>
                    <td className="max-w-md px-3 py-4 font-medium">
                      {hypothesis}
                    </td>
                    <td className="px-3 py-4">
                      <Badge variant="outline">{copy.awaitingLink}</Badge>
                    </td>
                    <td className="text-muted-foreground px-3 py-4">
                      {copy.noDirectEvidence}
                    </td>
                    <td className="px-3 py-4 font-medium text-rose-700 dark:text-rose-300">
                      {copy.highImpact}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="border-border border-t pt-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">{copy.evidenceLedger}</h2>
          <Badge className={statusTone(model.evidenceState)} variant="outline">
            {copy.evidenceStates[model.evidenceState]}
          </Badge>
        </div>
        {model.evidence.length === 0 ? (
          <p className="text-muted-foreground mt-4 text-sm">
            {copy.noEvidence}
          </p>
        ) : (
          <div className="mt-4 divide-y border-y">
            {model.evidence.map((entry) => (
              <div
                className="grid gap-3 py-4 md:grid-cols-[72px_1fr_auto]"
                key={entry.id}
              >
                <div className="font-mono text-xs font-semibold">
                  {entry.id}
                </div>
                <div>
                  <div className="text-sm leading-6">{entry.claim}</div>
                  {entry.limitation && (
                    <div className="text-muted-foreground mt-1 text-xs leading-5">
                      {copy.limitation}: {entry.limitation}
                    </div>
                  )}
                </div>
                <div className="md:text-right">
                  <Badge variant="outline">
                    {copy.evidenceLabels[entry.evidenceLabel]}
                  </Badge>
                  <div className="text-muted-foreground mt-2 text-xs">
                    {copy.sourceCount(entry.sourceUrls.length)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export function LaunchDecisionWorkspace({
  threadId,
  messages,
  isStreaming,
  onRecordValidationResult,
  onOpenGrowthAnalyst,
  onReturnToChat,
}: LaunchDecisionWorkspaceProps) {
  const { locale, t } = useI18n();
  const copy = t.launchDecision;
  const language = locale === "zh-CN" ? "zh" : "en";
  const { artifacts, select, setOpen } = useArtifacts();
  const evidencePath = findArtifact(artifacts, "evidence-ledger.json");
  const calendarPath = findArtifact(artifacts, "launch-calendar.csv");
  const evidenceArtifact = useArtifactContent({
    filepath: evidencePath,
    threadId,
    enabled: Boolean(evidencePath),
  });
  const calendarArtifact = useArtifactContent({
    filepath: calendarPath,
    threadId,
    enabled: Boolean(calendarPath),
  });
  const model = useMemo(
    () =>
      buildDecisionWorkspaceModel({
        messages,
        evidenceLedger: evidenceArtifact.content,
        launchCalendar: calendarArtifact.content,
      }),
    [messages, evidenceArtifact.content, calendarArtifact.content],
  );
  const [dialogOpen, setDialogOpen] = useState(false);
  const [draft, setDraft] = useState<ValidationDraft>({
    ...EMPTY_DRAFT,
    date: today(),
  });

  const openRecordDialog = (experiment = "") => {
    setDraft({ ...EMPTY_DRAFT, experiment, date: today() });
    setDialogOpen(true);
  };

  const submitResult = () => {
    if (!draft.experiment.trim() || !draft.observation.trim()) {
      return;
    }
    const message = formatValidationResultMessage(draft, language);
    void onRecordValidationResult({ text: message, files: [] });
    setDialogOpen(false);
  };

  if (!model.currentSpec) {
    return (
      <div
        className="flex size-full min-h-0 items-center justify-center px-6 pt-12"
        data-testid="launch-decision-workspace"
      >
        <div className="max-w-md text-center">
          <ClipboardCheckIcon className="text-muted-foreground mx-auto size-8" />
          <h1 className="mt-4 text-base font-semibold">{copy.emptyTitle}</h1>
          <p className="text-muted-foreground mt-2 text-sm leading-6">
            {copy.emptyDescription}
          </p>
          <Button className="mt-5" variant="outline" onClick={onReturnToChat}>
            {copy.returnToChat}
          </Button>
        </div>
      </div>
    );
  }

  const spec = model.currentSpec;
  const primaryRisk = spec.hypotheses[0] ?? copy.noCriticalRisk;
  const nextExperiment = model.experiments[0];
  const loadingArtifacts =
    evidenceArtifact.isLoading || calendarArtifact.isLoading;

  return (
    <div
      className="size-full min-h-0 overflow-y-auto pt-12"
      data-testid="launch-decision-workspace"
    >
      <div className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
        <header className="border-border border-b pb-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-semibold break-words">
                  {copy.workspaceTitle(spec.category)}
                </h1>
                <Badge
                  className={statusTone(model.evidenceState)}
                  variant="outline"
                >
                  {copy.evidenceStates[model.evidenceState]}
                </Badge>
                {model.pendingReassessment && (
                  <Badge
                    className="border-amber-600/30 bg-amber-500/10 text-amber-800 dark:text-amber-300"
                    variant="outline"
                  >
                    <FileClockIcon />
                    {copy.awaitingReassessment}
                  </Badge>
                )}
              </div>
              <p className="text-muted-foreground mt-2 max-w-3xl text-sm leading-6">
                {spec.decisionRationale || copy.noRationale}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={isStreaming}
                size="sm"
                variant="outline"
                onClick={() => {
                  const handoff = buildGrowthAnalystHandoff(model, language);
                  if (handoff) {
                    onOpenGrowthAnalyst(handoff);
                  }
                }}
              >
                <ExternalLinkIcon />
                {copy.openGrowthAnalyst}
              </Button>
              <Button
                disabled={isStreaming}
                size="sm"
                onClick={() => openRecordDialog()}
              >
                {isStreaming ? (
                  <Loader2Icon className="animate-spin" />
                ) : (
                  <PlusIcon />
                )}
                {copy.recordResult}
              </Button>
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryItem
              label={copy.currentRecommendation}
              value={copy.decisions[spec.decision]}
            />
            <SummaryItem label={copy.keyRisk} value={primaryRisk} danger />
            <SummaryItem
              label={copy.nextStep}
              value={displayValue(nextExperiment?.action, copy.noNextStep)}
            />
            <SummaryItem
              danger
              label={copy.stopCondition}
              value={displayValue(
                nextExperiment?.stopCondition,
                copy.noStopCondition,
              )}
            />
          </div>
        </header>

        <Tabs className="mt-5" defaultValue="overview">
          <div className="flex items-center justify-between gap-3 overflow-x-auto border-b">
            <TabsList className="h-10 shrink-0" variant="line">
              <TabsTrigger value="overview">{copy.tabs.overview}</TabsTrigger>
              <TabsTrigger value="experiments">
                {copy.tabs.experiments}
              </TabsTrigger>
              <TabsTrigger value="evidence">{copy.tabs.evidence}</TabsTrigger>
              <TabsTrigger value="deliverables">
                {copy.tabs.deliverables}
              </TabsTrigger>
            </TabsList>
            {loadingArtifacts && (
              <div className="text-muted-foreground flex shrink-0 items-center gap-2 text-xs">
                <Loader2Icon className="size-3.5 animate-spin" />
                {copy.loadingArtifacts}
              </div>
            )}
          </div>

          <TabsContent className="py-6" value="overview">
            <DecisionOverview copy={copy} model={model} />
          </TabsContent>
          <TabsContent className="py-6" value="experiments">
            <ExperimentsView
              copy={copy}
              experiments={model.experiments}
              onRecord={openRecordDialog}
            />
          </TabsContent>
          <TabsContent className="py-6" value="evidence">
            <EvidenceView copy={copy} model={model} />
          </TabsContent>
          <TabsContent className="py-6" value="deliverables">
            <section>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold">
                    {copy.deliverablesTitle}
                  </h2>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {copy.deliverablesDescription}
                  </p>
                </div>
                <Badge variant="outline">
                  {
                    LAUNCH_PACK_FILENAMES.filter((filename) =>
                      artifacts.some(
                        (filepath) => getFileName(filepath) === filename,
                      ),
                    ).length
                  }
                  /{LAUNCH_PACK_FILENAMES.length}
                </Badge>
              </div>
              <div className="mt-5 divide-y border-y">
                {LAUNCH_PACK_FILENAMES.map((filename) => {
                  const filepath = findArtifact(artifacts, filename);
                  return (
                    <div
                      className="flex min-h-14 items-center justify-between gap-3 py-3"
                      key={filename}
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        {filepath ? (
                          <FileCheck2Icon className="size-4 shrink-0 text-emerald-600" />
                        ) : (
                          <CircleAlertIcon className="text-muted-foreground size-4 shrink-0" />
                        )}
                        <span className="truncate font-mono text-xs">
                          {filename}
                        </span>
                      </div>
                      {filepath ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            select(filepath);
                            setOpen(true);
                          }}
                        >
                          {copy.openArtifact}
                          <ChevronRightIcon />
                        </Button>
                      ) : (
                        <span className="text-muted-foreground text-xs">
                          {copy.missingArtifact}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{copy.resultDialogTitle}</DialogTitle>
            <DialogDescription>
              {copy.resultDialogDescription}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <label className="grid gap-1.5 text-sm font-medium">
              {copy.experiment}
              <Input
                placeholder={copy.experimentPlaceholder}
                value={draft.experiment}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    experiment: event.target.value,
                  }))
                }
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1.5 text-sm font-medium">
                {copy.date}
                <Input
                  type="date"
                  value={draft.date}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      date: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="grid gap-1.5 text-sm font-medium">
                {copy.outcome}
                <Select
                  value={draft.outcome}
                  onValueChange={(value: ValidationOutcome) =>
                    setDraft((current) => ({ ...current, outcome: value }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(copy.outcomes) as ValidationOutcome[]).map(
                      (outcome) => (
                        <SelectItem key={outcome} value={outcome}>
                          {copy.outcomes[outcome]}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
              </label>
            </div>
            <label className="grid gap-1.5 text-sm font-medium">
              {copy.sampleDefinition}
              <Input
                placeholder={copy.samplePlaceholder}
                value={draft.sampleDefinition}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    sampleDefinition: event.target.value,
                  }))
                }
              />
            </label>
            <label className="grid gap-1.5 text-sm font-medium">
              {copy.observation}
              <Textarea
                className="min-h-28"
                placeholder={copy.observationPlaceholder}
                value={draft.observation}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    observation: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {copy.cancel}
            </Button>
            <Button
              disabled={!draft.experiment.trim() || !draft.observation.trim()}
              onClick={submitResult}
            >
              <CheckCircle2Icon />
              {copy.submitResult}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
