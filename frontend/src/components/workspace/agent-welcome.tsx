"use client";

import {
  BotIcon,
  CheckCircle2Icon,
  DatabaseIcon,
  FileSpreadsheetIcon,
  ShoppingBagIcon,
} from "lucide-react";
import { useState } from "react";

import { usePromptInputController } from "@/components/ai-elements/prompt-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type Agent } from "@/core/agents";
import {
  createGrowthAnalystDemoFiles,
  GROWTH_ANALYST_DEMO_SCENARIOS,
  GROWTH_ANALYST_DEMO_SCENARIO_IDS,
  isGrowthAnalystDemoFile,
  type GrowthAnalystDemoScenarioId,
} from "@/core/demo/growth-analyst";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

export function AgentWelcome({
  className,
  agent,
  agentName,
}: {
  className?: string;
  agent: Agent | null | undefined;
  agentName: string;
}) {
  const { t } = useI18n();
  const isEcomLaunch = agentName === "ecom-launch";
  const isDataInspector = agentName === "data-inspector";
  const displayName = isEcomLaunch
    ? t.agents.ecomLaunchName
    : isDataInspector
      ? t.agents.dataInspectorName
      : (agent?.name ?? agentName);
  const description = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeDescription
    : isDataInspector
      ? t.agents.dataInspectorWelcomeDescription
      : agent?.description;
  const Icon = isEcomLaunch
    ? ShoppingBagIcon
    : isDataInspector
      ? DatabaseIcon
      : BotIcon;

  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="bg-primary/10 flex h-12 w-12 items-center justify-center rounded-full">
        <Icon className="text-primary h-6 w-6" />
      </div>
      <div className="text-2xl font-bold">{displayName}</div>
      {description && (
        <p className="text-muted-foreground max-w-sm text-sm">{description}</p>
      )}
      {isEcomLaunch && (
        <div className="mt-1 flex max-w-md flex-wrap justify-center gap-1.5">
          {t.agents.ecomLaunchWelcomeBadges.map((badge) => (
            <Badge key={badge} variant="secondary" className="font-normal">
              {badge}
            </Badge>
          ))}
        </div>
      )}
      {isDataInspector && <GrowthAnalystDemoCard />}
    </div>
  );
}

function GrowthAnalystDemoCard() {
  const { t } = useI18n();
  const { attachments, textInput } = usePromptInputController();
  const demoCopy = t.agents.dataInspectorDemo;
  const [selectedScenarioId, setSelectedScenarioId] =
    useState<GrowthAnalystDemoScenarioId>("experiment");
  const selectedScenario = GROWTH_ANALYST_DEMO_SCENARIOS[selectedScenarioId];
  const selectedScenarioCopy = demoCopy.scenarios[selectedScenarioId];
  const loadedDemoAttachments = attachments.files.filter((file) =>
    isGrowthAnalystDemoFile(file.file),
  );
  const loadedDemoFiles = new Set(
    loadedDemoAttachments.map((file) => file.filename).filter(Boolean),
  );
  const hasLoadedDemoFiles = loadedDemoAttachments.length > 0;
  const isLoaded = selectedScenario.files.every((file) =>
    loadedDemoFiles.has(file),
  );

  const handleLoad = () => {
    if (!isLoaded) {
      for (const attachment of attachments.files) {
        if (isGrowthAnalystDemoFile(attachment.file)) {
          attachments.remove(attachment.id);
        }
      }
      attachments.add(createGrowthAnalystDemoFiles(selectedScenarioId));
    }
    textInput.setInput(selectedScenarioCopy.prompt);
  };

  const handleScenarioChange = (value: string) => {
    if (
      GROWTH_ANALYST_DEMO_SCENARIO_IDS.includes(
        value as GrowthAnalystDemoScenarioId,
      )
    ) {
      setSelectedScenarioId(value as GrowthAnalystDemoScenarioId);
    }
  };

  const loadButton = (
    <Button
      type="button"
      size="sm"
      variant={isLoaded ? "secondary" : "default"}
      onClick={handleLoad}
    >
      {isLoaded ? (
        <CheckCircle2Icon className="size-4" />
      ) : (
        <DatabaseIcon className="size-4" />
      )}
      {isLoaded ? demoCopy.loaded : demoCopy.load}
    </Button>
  );

  return (
    <div
      data-testid="growth-demo-data"
      className="border-border/70 bg-background/70 mt-3 w-full max-w-xl rounded-xl border p-3 text-left shadow-sm"
    >
      <div className="flex items-start gap-2.5">
        <div className="flex min-w-0 items-start gap-2.5">
          <div className="bg-primary/10 text-primary mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg">
            <FileSpreadsheetIcon className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold">{demoCopy.title}</div>
            <div className="text-muted-foreground text-xs">
              {demoCopy.description}
            </div>
          </div>
        </div>
      </div>
      <Tabs
        value={selectedScenarioId}
        onValueChange={handleScenarioChange}
        className="mt-3"
      >
        <TabsList
          aria-label={demoCopy.selectorLabel}
          className="grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-4"
        >
          {GROWTH_ANALYST_DEMO_SCENARIO_IDS.map((scenarioId) => (
            <TabsTrigger
              key={scenarioId}
              value={scenarioId}
              data-testid={`growth-demo-scenario-${scenarioId}`}
              className="h-8 px-2 text-xs"
            >
              {demoCopy.scenarios[scenarioId].label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div
        className={cn(
          "mt-2",
          hasLoadedDemoFiles && "flex items-end justify-between gap-3",
        )}
      >
        <div className="min-w-0">
          <div className="text-muted-foreground text-xs">
            {selectedScenarioCopy.description}
          </div>
          <div
            data-testid="growth-demo-files"
            className="mt-2 flex flex-wrap gap-1.5"
          >
            {selectedScenario.files.map((file) => (
              <Badge key={file} variant="outline" className="font-normal">
                {file}
              </Badge>
            ))}
          </div>
        </div>
        {hasLoadedDemoFiles && loadButton}
      </div>
      {!hasLoadedDemoFiles && (
        <>
          <div
            data-testid="growth-demo-preview"
            className="text-muted-foreground mt-2 text-[11px]"
          >
            {selectedScenarioCopy.preview}
          </div>
          <div className="mt-2 flex items-end justify-between gap-3">
            <p className="text-muted-foreground text-[11px]">
              {demoCopy.note}
            </p>
            {loadButton}
          </div>
        </>
      )}
    </div>
  );
}
