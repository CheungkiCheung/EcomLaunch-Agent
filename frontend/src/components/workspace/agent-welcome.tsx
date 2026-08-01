"use client";

import {
  BotIcon,
  ChartNoAxesCombinedIcon,
  ShoppingBagIcon,
} from "lucide-react";

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
  const isStoreOperator = agentName === "store-operator";
  const displayName = isEcomLaunch
    ? t.agents.ecomLaunchName
    : isStoreOperator
      ? t.agents.storeOperatorName
      : (agent?.name ?? agentName);
  const description = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeDescription
    : isStoreOperator
      ? t.agents.storeOperatorWelcomeDescription
      : agent?.description;
  const badges = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeBadges
    : isStoreOperator
      ? t.agents.storeOperatorWelcomeBadges
      : [];
  const Icon = isEcomLaunch
    ? ShoppingBagIcon
    : isStoreOperator
      ? ChartNoAxesCombinedIcon
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
      {badges.length > 0 && (
        <div className="mt-1 flex max-w-md flex-wrap justify-center gap-1.5">
          {badges.map((badge) => (
            <Badge key={badge} variant="secondary" className="font-normal">
              {badge}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
