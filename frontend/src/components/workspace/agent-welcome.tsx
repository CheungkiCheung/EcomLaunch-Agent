"use client";

import { BotIcon, DatabaseIcon, ShoppingBagIcon, ZapIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { type Agent } from "@/core/agents";
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
  const isOpenskufast = agentName === "openskufast";
  const displayName = isEcomLaunch
    ? t.agents.ecomLaunchName
    : isDataInspector
      ? t.agents.dataInspectorName
      : isOpenskufast
        ? t.agents.openskufastName
        : (agent?.name ?? agentName);
  const description = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeDescription
    : isDataInspector
      ? t.agents.dataInspectorWelcomeDescription
      : isOpenskufast
        ? t.agents.openskufastWelcomeDescription
        : agent?.description;
  const Icon = isEcomLaunch
    ? ShoppingBagIcon
    : isDataInspector
      ? DatabaseIcon
      : isOpenskufast
        ? ZapIcon
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
      {isOpenskufast && (
        <div className="mt-1 flex max-w-md flex-wrap justify-center gap-1.5">
          {t.agents.openskufastWelcomeBadges.map((badge) => (
            <Badge key={badge} variant="secondary" className="font-normal">
              {badge}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
